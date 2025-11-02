#!/usr/bin/env python3
"""
Cocoaテストランナー
包括的テストスイートの実行とレポート生成
"""
import os
import sys
import time
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List


# プロジェクトルートをPythonパスに追加
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "main"))

def setup_test_environment():
    """テスト環境をセットアップ"""
    print("🔧 テスト環境をセットアップしています...")
    # 必要なディレクトリ作成
    dirs_to_create = [
        "logs",
        "temp",
        "backups",
        "data",
        "config",
        "tests/reports"
    ]

    for dir_path in dirs_to_create:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    # テスト用設定ファイル作成
    test_config = {
        "environment": "test",
        "database": {
            "type": "sqlite",
            "database": "data/test.db"
        },
        "logging": {
            "level": "INFO",
            "enable_console": False
        }
    }

    config_path = Path("config/test_config.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(test_config, f, indent=2)

    print("✅ テスト環境のセットアップが完了しました")


@dataclass(frozen=True)
class CommandContext:
    parser: argparse.ArgumentParser
    config_manager: "ConfigManager"
    args: argparse.Namespace

    @property
    def config(self) -> RunnerConfig:
        return self.config_manager.ensure_latest()

    @property
    def effective_verbosity(self) -> int:
        if self.args.verbosity is not None:
            return self.args.verbosity
        return self.config.default_verbosity

    def resolve_pattern(self, pattern: Optional[str]) -> str:
        candidate = pattern if pattern is not None else self.config.default_pattern
        try:
            return validate_pattern(candidate)
        except argparse.ArgumentTypeError as exc:
            raise TestRunnerError(
                "`default_pattern` が不正です / Invalid value for `default_pattern`"
            ) from exc


class ConfigManager:
    def __init__(self, config_path: Path) -> None:
        self._path = config_path
        self._config = RunnerConfig()
        self._mtime: float | None = None

    def ensure_latest(self) -> RunnerConfig:
        current_mtime = self._get_mtime()
        if current_mtime != self._mtime:
            self._config = load_runner_config(self._path)
            self._mtime = current_mtime
        return self._config

    def _get_mtime(self) -> float | None:
        try:
            return self._path.stat().st_mtime
        except FileNotFoundError:
            return None


def validate_verbosity(value: str) -> int:
    """--verbosity引数を検証して返す。"""
    try:
        level = int(value)
    except ValueError as exc:  # pragma: no cover - argparse経由
        raise argparse.ArgumentTypeError(
            "`--verbosity` は整数で指定してください / "
            "`--verbosity` must be an integer"
        ) from exc

    if not 0 <= level <= 3:
        raise argparse.ArgumentTypeError(
            "`--verbosity` は0から3の範囲で指定してください / "
            "`--verbosity` must be between 0 and 3"
        )

    return level


def validate_pattern(value: str) -> str:
    """--pattern引数を検証して返す。"""
    candidate = value.strip()
    if not candidate:
        raise argparse.ArgumentTypeError(
            "`--pattern` に空文字は指定できません / "
            "`--pattern` must not be empty"
        )
    return candidate


def validate_config_verbosity(value: Any) -> int:
    if not isinstance(value, int):
        raise TestRunnerError(
            "`default_verbosity` は整数で指定してください / "
            "`default_verbosity` must be an integer"
        )
    if not 0 <= value <= 3:
        raise TestRunnerError(
            "`default_verbosity` は0から3の範囲で指定してください / "
            "`default_verbosity` must be between 0 and 3"
        )
    return value


def ensure_pythonpath(extra_paths: Iterable[Path] | None = None) -> None:
    """プロジェクトルートと追加パスをPythonパスに追加する。"""
    candidates = [PROJECT_ROOT, PROJECT_ROOT / "main"]
    if extra_paths:
        candidates.extend(extra_paths)
    for path in candidates:
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def discover_tests(config: RunnerConfig, pattern: str) -> unittest.TestSuite:
    """指定したパターンでテストスイートをディスカバリする。"""
    loader = unittest.TestLoader()
    try:
        return loader.discover(str(config.tests_dir), pattern=pattern)
    except OSError as exc:
        raise TestRunnerError(
            "テストの探索に失敗しました: "
            f"{config.tests_dir}\nFailed to discover tests inside: "
            f"{config.tests_dir}"
        ) from exc


def list_tests(config: RunnerConfig) -> list[str]:
    """利用可能なテストモジュール名（拡張子なし）を列挙する。"""
    tests_dir = config.tests_dir
    if not tests_dir.exists():
        return []
    return sorted(
        path.stem
        for path in tests_dir.glob(config.default_pattern)
        if path.is_file()
    )


def config_tests_package_name(config: RunnerConfig) -> str:
    try:
        relative = config.tests_dir.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise TestRunnerError(
            "テストディレクトリはプロジェクト配下に配置してください: "
            f"{config.tests_dir}\nTests directory must reside under the project root: "
            f"{config.tests_dir}"
        ) from exc

    parts = [part for part in relative.parts if part not in {"", "."}]
    if not parts:
        raise TestRunnerError(
            "テストディレクトリのパッケージ名を解決できません / "
            "Unable to resolve package name for the tests directory"
        )

    for part in parts:
        if not part.isidentifier():
            raise TestRunnerError(
                "パッケージ名に無効なディレクトリ名が含まれています: "
                f"{part}\nInvalid package component in tests directory: {part}"
            )

def run_tests_in_parallel(suite: unittest.TestSuite, max_workers: int = 4) -> unittest.TestResult:
    """テストスイートを並列実行する。"""
    def run_test_case(test_case):
        """個別のテストケースを実行する。"""
        result = unittest.TestResult()
        try:
            test_case(result)
            return result
        except Exception as e:
            result.addError(test_case, sys.exc_info())
            return result

    # テストケースをグループ化
    test_cases = list(suite)
    if not test_cases:
        return unittest.TestResult()

    # 並列実行でテストケースを実行
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_test = {executor.submit(run_test_case, test_case): test_case for test_case in test_cases}
        results = []

        for future in concurrent.futures.as_completed(future_to_test):
            test_case = future_to_test[future]
            try:
                result = future.result()
                results.append((test_case, result))
            except Exception as e:
                # エラーハンドリング
                error_result = unittest.TestResult()
                error_result.addError(test_case, sys.exc_info())
                results.append((test_case, error_result))

    # 結果を集約
    final_result = unittest.TestResult()
    for test_case, result in results:
        final_result.testsRun += result.testsRun
        final_result.failures.extend(result.failures)
        final_result.errors.extend(result.errors)
        final_result.skipped.extend(result.skipped)

class JsonLogger:
    """JSON形式でログを出力する。"""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path
        self.log_file = None
        if log_path:
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                self.log_file = log_path.open("a", encoding="utf-8")
            except OSError:
                print(f"ログファイルの作成に失敗しました: {log_path}")

    def log(self, level: str, message: str, **kwargs) -> None:
        """JSON形式でログを出力する。"""
        log_entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            **kwargs
        }

        # コンソール出力
        print(f"[{level}] {message}")

        # ファイル出力
        if self.log_file:
            try:
                self.log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                self.log_file.flush()
            except OSError:
                pass  # ログファイルの書き込みエラーは無視

    def info(self, message: str, **kwargs) -> None:
        """INFOレベルのログを出力する。"""
        self.log("INFO", message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """ERRORレベルのログを出力する。"""
        self.log("ERROR", message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """WARNINGレベルのログを出力する。"""
        self.log("WARNING", message, **kwargs)

    def close(self) -> None:
        """ログファイルを閉じる。"""
class SelfAdaptingMonitor:
    """自己適応型の監視システム。"""

    def __init__(self, config: RunnerConfig, json_logger: Optional[JsonLogger] = None):
        self.config = config
        self.json_logger = json_logger
        self.baseline_metrics = {}
        self.adaptation_history = []
        self.alert_count = 0

    def start_monitoring(self) -> None:
        """監視を開始する。"""
        if self.json_logger:
            self.json_logger.info("自己適応監視を開始します")

    def check_thresholds(self, metrics: PerformanceMetrics) -> dict[str, bool]:
        """しきい値チェックを実行し、違反を検知する。"""
        violations = {}
        thresholds = self.config.monitoring_thresholds

        # CPU使用率チェック
        if metrics.average_cpu > thresholds["cpu_percent"]:
            violations["cpu_percent"] = True

        # メモリ使用率チェック
        if metrics.max_memory > thresholds["memory_percent"]:
            violations["memory_percent"] = True

        # テスト実行時間チェック
        if metrics.total_tests > 0:
            avg_time_per_test = metrics.total_time / metrics.total_tests
            if avg_time_per_test > thresholds["execution_time_per_test"]:
                violations["execution_time_per_test"] = True

        # エラーレートチェック
        if metrics.total_tests > 0:
            error_rate = (metrics.failed_tests / metrics.total_tests) * 100
            if error_rate > thresholds["error_rate"]:
                violations["error_rate"] = True

        return violations

    def adapt_thresholds(self, metrics: PerformanceMetrics, violations: dict[str, bool]) -> None:
        """違反に基づいてしきい値を適応させる。"""
        if not violations:
            return

        thresholds = self.config.monitoring_thresholds.copy()

        # ベースラインメトリクスを更新
        if not self.baseline_metrics:
            self.baseline_metrics = {
                "average_cpu": metrics.average_cpu,
                "max_memory": metrics.max_memory,
                "avg_time_per_test": metrics.total_time / max(metrics.total_tests, 1),
            }

        # しきい値を適応
        adaptation_factor = 1.1  # 10%緩和

        for violation_type in violations:
            if violation_type == "cpu_percent":
                thresholds["cpu_percent"] = min(thresholds["cpu_percent"] * adaptation_factor, 95.0)
            elif violation_type == "memory_percent":
                thresholds["memory_percent"] = min(thresholds["memory_percent"] * adaptation_factor, 95.0)
            elif violation_type == "execution_time_per_test":
                thresholds["execution_time_per_test"] *= adaptation_factor
            elif violation_type == "error_rate":
                thresholds["error_rate"] = min(thresholds["error_rate"] * adaptation_factor, 50.0)

        # 適応履歴を記録
        self.adaptation_history.append({
            "timestamp": time.time(),
            "violations": list(violations.keys()),
            "old_thresholds": self.config.monitoring_thresholds.copy(),
            "new_thresholds": thresholds.copy(),
        })

        # 設定を更新（実際の更新はConfigManagerで行う）
        if self.json_logger:
            self.json_logger.info("しきい値を適応しました", violations=violations, new_thresholds=thresholds)

    def generate_alert(self, violations: dict[str, bool], metrics: PerformanceMetrics) -> None:
        """アラートを生成する。"""
        self.alert_count += 1

        alert_message = "パフォーマンスしきい値違反が検知されました"
        if self.json_logger:
            self.json_logger.warning(alert_message, violations=violations, metrics=metrics.to_dict())

        print(f"⚠️  {alert_message}:")
        for violation in violations:
            if violation == "cpu_percent":
                print(f"  - CPU使用率が{self.config.monitoring_thresholds['cpu_percent']}%を超えました (現在: {metrics.average_cpu:.1f}%)")
            elif violation == "memory_percent":
                print(f"  - メモリ使用率が{self.config.monitoring_thresholds['memory_percent']}%を超えました (現在: {metrics.max_memory:.1f}%)")
            elif violation == "execution_time_per_test":
                avg_time = metrics.total_time / max(metrics.total_tests, 1)
                print(f"  - テスト実行時間が{self.config.monitoring_thresholds['execution_time_per_test']:.1f}秒を超えました (現在: {avg_time:.2f}秒)")
            elif violation == "error_rate":
                error_rate = (metrics.failed_tests / max(metrics.total_tests, 1)) * 100
class AutoTestGenerator:
    """テストケースを自動生成する。"""

    def __init__(self, config: RunnerConfig, json_logger: Optional[JsonLogger] = None):
        self.config = config
        self.json_logger = json_logger
        self.generated_tests = []

    def discover_modules(self) -> list[str]:
        """自動生成対象のモジュールを発見する。"""
        modules = []
        config = self.config.auto_test_config

        for module_name in config["enabled_modules"]:
            if module_name == "main":
                # mainディレクトリのPythonファイルを検索
                main_dir = PROJECT_ROOT / "main"
                if main_dir.exists():
                    for py_file in main_dir.glob("*.py"):
                        if not py_file.name.startswith("__") and py_file.name != "main.py":
                            modules.append(py_file.stem)
            else:
                # 特定のモジュール
                modules.append(module_name)

        return modules

    def analyze_module(self, module_name: str) -> dict[str, Any]:
        """モジュールを分析してテスト生成情報を取得する。"""
        try:
            module = importlib.import_module(f"main.{module_name}")
        except ImportError:
            return {"error": f"Module {module_name} not found"}

        analysis = {
            "module_name": module_name,
            "functions": [],
            "classes": [],
            "complexity": 0,
        }

        # 関数とクラスの情報を収集
        for name in dir(module):
            if name.startswith("_"):
                continue

            obj = getattr(module, name)
            if callable(obj):
                if inspect.isfunction(obj):
                    analysis["functions"].append({
                        "name": name,
                        "signature": str(inspect.signature(obj)) if obj.__code__ else "N/A",
                    })
                elif inspect.isclass(obj):
                    analysis["classes"].append({
                        "name": name,
                        "methods": [m for m in dir(obj) if not m.startswith("_") and callable(getattr(obj, m))],
                    })

        analysis["complexity"] = len(analysis["functions"]) + len(analysis["classes"])
        return analysis

    def generate_unit_tests(self, module_analysis: dict[str, Any]) -> list[str]:
        """ユニットテストを生成する。"""
        tests = []
        module_name = module_analysis["module_name"]

        # 関数に対するテスト
        for func in module_analysis["functions"]:
            test_code = self._generate_function_test(module_name, func)
            tests.append(test_code)

        # クラスに対するテスト
        for cls in module_analysis["classes"]:
            test_code = self._generate_class_test(module_name, cls)
            tests.append(test_code)

        return tests

    def _generate_function_test(self, module_name: str, func: dict[str, Any]) -> str:
        """関数に対するテストケースを生成する。"""
        return f'''
def test_{func["name"]}():
    """Test for {func["name"]} function."""
    # TODO: Implement test for {func["name"]}
    # This is an auto-generated test stub
    assert True  # Replace with actual test logic
'''

    def _generate_class_test(self, module_name: str, cls: dict[str, Any]) -> str:
        """クラスに対するテストケースを生成する。"""
        return f'''
def test_{cls["name"]}():
    """Test for {cls["name"]} class."""
    # TODO: Implement test for {cls["name"]}
    # This is an auto-generated test stub
    assert True  # Replace with actual test logic
'''

    def generate_integration_tests(self, modules: list[str]) -> list[str]:
        """統合テストを生成する。"""
        tests = []

        for module_name in modules:
            test_code = f'''
def test_{module_name}_integration():
    """Integration test for {module_name} module."""
    # TODO: Implement integration test for {module_name}
    # This is an auto-generated test stub
    assert True  # Replace with actual integration test logic
'''
            tests.append(test_code)

        return tests

    def create_test_file(self, module_name: str, test_content: str) -> Path:
        """テストファイルを作成する。"""
        test_file = PROJECT_ROOT / "tests" / f"test_{module_name}.py"

        # 既存のテストファイルがある場合はバックアップ
        if test_file.exists():
            backup_file = PROJECT_ROOT / "tests" / f"test_{module_name}_backup.py"
            import shutil
            shutil.copy2(test_file, backup_file)
            if self.json_logger:
                self.json_logger.info("既存のテストファイルをバックアップしました", file=str(backup_file))

        # 新しいテストファイルを作成
        with test_file.open("w", encoding="utf-8") as f:
            f.write(f'''"""Auto-generated tests for {module_name} module."""

import pytest
from main import {module_name}

{test_content}
''')

        self.generated_tests.append(str(test_file))
        if self.json_logger:
            self.json_logger.info("テストファイルを生成しました", module=module_name, file=str(test_file))

        return test_file

    def run_generation(self) -> dict[str, Any]:
        """テスト生成を実行する。"""
        if self.json_logger:
            self.json_logger.info("テストケース自動生成を開始します")

        modules = self.discover_modules()
        results = {
            "generated_tests": [],
            "analyzed_modules": [],
            "errors": [],
        }

        for module_name in modules:
            try:
                analysis = self.analyze_module(module_name)
                results["analyzed_modules"].append(analysis)

                # テスト生成の閾値チェック
                if analysis["complexity"] > 0 and analysis["complexity"] <= self.config.auto_test_config["max_tests_per_module"]:
                    # ユニットテスト生成
                    unit_tests = self.generate_unit_tests(analysis)
                    if unit_tests:
                        test_content = "\n".join(unit_tests)
                        test_file = self.create_test_file(module_name, test_content)
                        results["generated_tests"].append({
                            "module": module_name,
                            "file": str(test_file),
                            "test_count": len(unit_tests),
                        })

                    # 統合テスト生成
                    if "integration" in self.config.auto_test_config["test_types"]:
                        integration_tests = self.generate_integration_tests([module_name])
                        if integration_tests:
                            test_content = "\n".join(integration_tests)
                            # 統合テストは別ファイルに保存するか、既存ファイルに追加
                            test_file = self.create_test_file(f"{module_name}_integration", test_content)
                            results["generated_tests"].append({
                                "module": f"{module_name}_integration",
                                "file": str(test_file),
                                "test_count": len(integration_tests),
                            })

            except Exception as e:
                error_msg = f"Failed to generate tests for {module_name}: {str(e)}"
                results["errors"].append(error_msg)
                if self.json_logger:
                    self.json_logger.error(error_msg)

        if self.json_logger:
            self.json_logger.info("テストケース自動生成を完了しました", results=results)

class TestRollbackManager:
    """テスト実行のロールバックを管理する。"""

    def __init__(self, config: RunnerConfig, json_logger: Optional[JsonLogger] = None):
        self.config = config
        self.json_logger = json_logger
        self.backup_dir = PROJECT_ROOT / config.rollback_config["backup_dir"]
        self.backup_dir.mkdir(exist_ok=True)

    def create_backup(self, test_results: unittest.TestResult, timestamp: str) -> str:
        """テスト実行前の状態をバックアップする。"""
        backup_info = {
            "timestamp": timestamp,
            "test_results": {
                "tests_run": test_results.testsRun,
                "failures": len(test_results.failures),
                "errors": len(test_results.errors),
                "was_successful": test_results.wasSuccessful(),
            },
            "config_snapshot": {
                "monitoring_thresholds": self.config.monitoring_thresholds,
                "auto_test_config": self.config.auto_test_config,
            },
        }

        backup_file = self.backup_dir / f"test_backup_{timestamp}.json"
        try:
            with backup_file.open("w", encoding="utf-8") as f:
                json.dump(backup_info, f, indent=2, ensure_ascii=False)
            if self.json_logger:
                self.json_logger.info("テストバックアップを作成しました", backup_file=str(backup_file))
            return str(backup_file)
        except OSError as e:
            if self.json_logger:
                self.json_logger.error("バックアップの作成に失敗しました", error=str(e))
            return ""

    def cleanup_old_backups(self) -> None:
        """古いバックアップを削除する。"""
        max_backups = self.config.rollback_config["max_backups"]

        try:
            backup_files = sorted(
                [f for f in self.backup_dir.glob("test_backup_*.json")],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )

            if len(backup_files) > max_backups:
                for old_backup in backup_files[max_backups:]:
                    old_backup.unlink()
                    if self.json_logger:
                        self.json_logger.info("古いバックアップを削除しました", backup_file=str(old_backup))
        except OSError as e:
            if self.json_logger:
                self.json_logger.error("バックアップのクリーンアップに失敗しました", error=str(e))

    def rollback_to_backup(self, backup_file: str) -> bool:
        """指定されたバックアップにロールバックする。"""
        backup_path = Path(backup_file)
        if not backup_path.exists():
            if self.json_logger:
                self.json_logger.error("指定されたバックアップファイルが存在しません", backup_file=backup_file)
            return False

        try:
            with backup_path.open("r", encoding="utf-8") as f:
                backup_data = json.load(f)

            # 設定を復元
            if self.json_logger:
                self.json_logger.info("バックアップから設定を復元しました", backup_file=backup_file)

            return True
        except (OSError, json.JSONDecodeError) as e:
            if self.json_logger:
                self.json_logger.error("バックアップからの復元に失敗しました", error=str(e))
            return False

    def list_backups(self) -> list[dict[str, Any]]:
        """利用可能なバックアップの一覧を取得する。"""
        backups = []

        try:
            for backup_file in self.backup_dir.glob("test_backup_*.json"):
                with backup_file.open("r", encoding="utf-8") as f:
                    backup_data = json.load(f)
                    backups.append({
                        "file": str(backup_file),
                        "timestamp": backup_data["timestamp"],
                        "test_results": backup_data["test_results"],
                    })
        except (OSError, json.JSONDecodeError) as e:
            if self.json_logger:
                self.json_logger.error("バックアップ一覧の取得に失敗しました", error=str(e))

        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)

    def should_create_backup(self, test_results: unittest.TestResult) -> bool:
        """バックアップを作成すべきかを判定する。"""
        config = self.config.rollback_config

        if not config["backup_on_failure"]:
            return False

        # テストが失敗した場合にバックアップを作成
        return not test_results.wasSuccessful()

    def should_rollback(self, test_results: unittest.TestResult) -> bool:
        """ロールバックすべきかを判定する。"""
        config = self.config.rollback_config

        if not config["rollback_on_error"]:
            return False

        # エラーが発生した場合にロールバック
class DependencyHealthChecker:
    """依存関係の健全性をチェックする。"""

    def __init__(self, config: RunnerConfig, json_logger: Optional[JsonLogger] = None):
        self.config = config
        self.json_logger = json_logger
        self.health_report = {
            "python_version": sys.version,
            "platform": sys.platform,
            "required_modules": {},
            "optional_modules": {},
            "system_resources": {},
            "overall_health": "unknown",
        }

    def check_python_version(self) -> tuple[bool, str]:
        """Pythonバージョンをチェックする。"""
        current_version = sys.version_info
        min_version = tuple(map(int, self.config.dependency_checks["min_python_version"].split(".")))

        is_compatible = current_version >= min_version
        message = f"Python {'.'.join(map(str, current_version[:3]))} (required: {self.config.dependency_checks['min_python_version']})"

        self.health_report["python_version_check"] = {
            "compatible": is_compatible,
            "message": message,
        }

        return is_compatible, message

    def check_required_modules(self) -> tuple[bool, str]:
        """必須モジュールをチェックする。"""
        missing_modules = []
        available_modules = {}

        for module_name in self.config.dependency_checks["required_modules"]:
            try:
                module = importlib.import_module(module_name)
                available_modules[module_name] = {
                    "available": True,
                    "version": getattr(module, "__version__", "N/A"),
                }
            except ImportError:
                missing_modules.append(module_name)
                available_modules[module_name] = {
                    "available": False,
                    "version": "N/A",
                }

        self.health_report["required_modules"] = available_modules

        if missing_modules:
            message = f"Missing required modules: {', '.join(missing_modules)}"
            return False, message
        else:
            message = "All required modules are available"
            return True, message

    def check_optional_modules(self) -> tuple[bool, str]:
        """オプションのモジュールをチェックする。"""
        available_modules = {}

        for module_name in self.config.dependency_checks["optional_modules"]:
            try:
                module = importlib.import_module(module_name)
                available_modules[module_name] = {
                    "available": True,
                    "version": getattr(module, "__version__", "N/A"),
                }
            except ImportError:
                available_modules[module_name] = {
                    "available": False,
                    "version": "N/A",
                }

        self.health_report["optional_modules"] = available_modules

        available_count = sum(1 for m in available_modules.values() if m["available"])
        total_count = len(available_modules)

        message = f"{available_count}/{total_count} optional modules available"
        return True, message  # オプションのモジュールは必須ではない

    def check_system_resources(self) -> tuple[bool, str]:
        """システムリソースをチェックする。"""
        resources = {}

        # メモリチェック
        try:
            import psutil
            memory = psutil.virtual_memory()
            available_memory_mb = memory.available / 1024 / 1024
            min_memory_mb = self.config.dependency_checks["min_memory_mb"]

            resources["memory"] = {
                "available_mb": available_memory_mb,
                "required_mb": min_memory_mb,
                "sufficient": available_memory_mb >= min_memory_mb,
            }
        except ImportError:
            resources["memory"] = {
                "available_mb": "unknown",
                "required_mb": min_memory_mb,
                "sufficient": "unknown",
            }

        # ディスクスペースチェック
        try:
            disk = psutil.disk_usage(PROJECT_ROOT)
            available_disk_mb = disk.free / 1024 / 1024
            min_disk_mb = self.config.dependency_checks["min_disk_space_mb"]

            resources["disk"] = {
                "available_mb": available_disk_mb,
                "required_mb": min_disk_mb,
                "sufficient": available_disk_mb >= min_disk_mb,
            }
        except (ImportError, OSError):
            resources["disk"] = {
                "available_mb": "unknown",
                "required_mb": min_disk_mb,
                "sufficient": "unknown",
            }

        self.health_report["system_resources"] = resources

        # 全体的な判定
        memory_ok = resources["memory"].get("sufficient", True)
        disk_ok = resources["disk"].get("sufficient", True)

        if memory_ok and disk_ok:
            message = "System resources are sufficient"
            return True, message
        else:
            issues = []
            if not memory_ok:
                issues.append(f"insufficient memory ({resources['memory']['available_mb']:.0f}MB < {resources['memory']['required_mb']}MB)")
            if not disk_ok:
                issues.append(f"insufficient disk space ({resources['disk']['available_mb']:.0f}MB < {resources['disk']['required_mb']}MB)")

            message = f"System resource issues: {', '.join(issues)}"
            return False, message

    def run_health_check(self) -> dict[str, Any]:
        """依存関係の健全性チェックを実行する。"""
        if self.json_logger:
            self.json_logger.info("依存関係健全性チェックを開始します")

        results = {
            "python_version": self.check_python_version(),
            "required_modules": self.check_required_modules(),
            "optional_modules": self.check_optional_modules(),
            "system_resources": self.check_system_resources(),
        }

        # 全体的な健全性を判定
        all_healthy = all(result[0] for result in results.values() if isinstance(result, tuple))
        self.health_report["overall_health"] = "healthy" if all_healthy else "unhealthy"

        if self.json_logger:
            self.json_logger.info("依存関係健全性チェックを完了しました", overall_health=self.health_report["overall_health"])

        return self.health_report

    def print_health_report(self) -> None:
        """健全性レポートを表示する。"""
        print("\n=== 依存関係健全性レポート ===")
        print(f"Pythonバージョン: {self.health_report['python_version_check']['message']}")
        print(f"必須モジュール: {self.health_report['required_modules']}")
        print(f"オプションのモジュール: {self.health_report['optional_modules']}")
        print(f"システムリソース: {self.health_report['system_resources']}")
        print(f"全体的な健全性: {self.health_report['overall_health']}")

class MetricsTrendAnalyzer:
    """メトリクスのトレンドを分析・可視化する。"""

    def __init__(self, config: RunnerConfig, json_logger: Optional[JsonLogger] = None):
        self.config = config
        self.json_logger = json_logger
        self.history_dir = PROJECT_ROOT / config.metrics_config["history_dir"]
        self.history_dir.mkdir(exist_ok=True)

    def save_metrics(self, metrics: PerformanceMetrics, test_result: unittest.TestResult) -> str:
        """メトリクスを履歴に保存する。"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        metrics_data = {
            "timestamp": timestamp,
            "metrics": metrics.to_dict(),
            "test_result": {
                "tests_run": test_result.testsRun,
                "failures": len(test_result.failures),
                "errors": len(test_result.errors),
                "was_successful": test_result.wasSuccessful(),
            },
            "system_info": {
                "python_version": sys.version,
                "platform": sys.platform,
            },
        }

        metrics_file = self.history_dir / f"metrics_{timestamp}.json"
        try:
            with metrics_file.open("w", encoding="utf-8") as f:
                json.dump(metrics_data, f, indent=2, ensure_ascii=False)
            if self.json_logger:
                self.json_logger.info("メトリクスを保存しました", metrics_file=str(metrics_file))
            return str(metrics_file)
        except OSError as e:
            if self.json_logger:
                self.json_logger.error("メトリクスの保存に失敗しました", error=str(e))
            return ""

    def load_metrics_history(self, days: int = 30) -> list[dict[str, Any]]:
        """履歴メトリクスを読み込む。"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        metrics_history = []

        try:
            for metrics_file in self.history_dir.glob("metrics_*.json"):
                if metrics_file.stat().st_mtime < cutoff_time:
                    continue

                with metrics_file.open("r", encoding="utf-8") as f:
                    metrics_data = json.load(f)
                    metrics_history.append(metrics_data)
        except (OSError, json.JSONDecodeError) as e:
            if self.json_logger:
                self.json_logger.error("メトリクス履歴の読み込みに失敗しました", error=str(e))

        return sorted(metrics_history, key=lambda x: x["timestamp"])

    def analyze_trends(self, metrics_history: list[dict[str, Any]]) -> dict[str, Any]:
        """メトリクスのトレンドを分析する。"""
        if len(metrics_history) < 2:
            return {"error": "Insufficient data for trend analysis"}

        # 時系列データを抽出
        timestamps = [m["timestamp"] for m in metrics_history]
        total_times = [m["metrics"]["total_time"] for m in metrics_history]
        cpu_usages = [m["metrics"]["average_cpu_percent"] for m in metrics_history]
        memory_usages = [m["metrics"]["max_memory_mb"] for m in metrics_history]
        test_counts = [m["metrics"]["total_tests"] for m in metrics_history]
        success_rates = [
            (m["metrics"]["passed_tests"] / max(m["metrics"]["total_tests"], 1)) * 100
            for m in metrics_history
        ]

        # トレンド分析
        trends = {
            "execution_time": self._calculate_trend(total_times),
            "cpu_usage": self._calculate_trend(cpu_usages),
            "memory_usage": self._calculate_trend(memory_usages),
            "test_count": self._calculate_trend(test_counts),
            "success_rate": self._calculate_trend(success_rates),
        }

        return {
            "timestamps": timestamps,
            "trends": trends,
            "summary": self._generate_summary(trends),
        }

    def _calculate_trend(self, values: list[float]) -> dict[str, Any]:
        """値のトレンドを計算する。"""
        if len(values) < 2:
            return {"trend": "insufficient_data", "change_percent": 0}

        # 線形トレンドを計算
        import numpy as np
        x = np.arange(len(values))
        y = np.array(values)

        # 線形回帰
        slope, intercept = np.polyfit(x, y, 1)

        # パーセント変化
        first_value = values[0]
        last_value = values[-1]
        change_percent = ((last_value - first_value) / max(first_value, 1)) * 100

        trend_direction = "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"

        return {
            "slope": slope,
            "change_percent": change_percent,
            "trend": trend_direction,
            "first_value": first_value,
            "last_value": last_value,
        }

    def _generate_summary(self, trends: dict[str, dict[str, Any]]) -> dict[str, str]:
        """トレンドのサマリーを生成する。"""
        summary = {}

        for metric, trend_data in trends.items():
            if trend_data.get("trend") == "insufficient_data":
                summary[metric] = "データ不足"
            else:
                change = trend_data["change_percent"]
                direction = trend_data["trend"]
                if direction == "increasing":
                    summary[metric] = f"上昇傾向 (+{change:.1f}%)"
                elif direction == "decreasing":
                    summary[metric] = f"下降傾向 ({change:.1f}%)"
                else:
                    summary[metric] = "安定"

        return summary

    def print_trend_report(self, analysis: dict[str, Any]) -> None:
        """トレンドレポートを表示する。"""
        print("\n=== メトリクストレンドレポート ===")
        print(f"分析期間: {len(analysis['timestamps'])}回の実行")

        for metric, trend in analysis["trends"].items():
            if trend["trend"] != "insufficient_data":
                print(f"\n{metric}:")
                print(f"  トレンド: {trend['trend']}")
                print(f"  変化率: {trend['change_percent']:.1f}%")
                print(f"  初回値: {trend['first_value']:.2f}")
                print(f"  最終値: {trend['last_value']:.2f}")

        print("\n=== サマリー ===")
        for metric, status in analysis["summary"].items():
            print(f"  {metric}: {status}")

    def cleanup_old_metrics(self) -> None:
        """古いメトリクスファイルを削除する。"""
        max_days = self.config.metrics_config["max_history_days"]
        cutoff_time = time.time() - (max_days * 24 * 60 * 60)

        try:
            for metrics_file in self.history_dir.glob("metrics_*.json"):
                if metrics_file.stat().st_mtime < cutoff_time:
                    metrics_file.unlink()
                    if self.json_logger:
                        self.json_logger.info("古いメトリクスファイルを削除しました", metrics_file=str(metrics_file))
        except OSError as e:
            if self.json_logger:
                self.json_logger.error("メトリクスファイルのクリーンアップに失敗しました", error=str(e))
    """テストスイートを実行して終了コードと結果を返す。"""
    if json_logger:
        json_logger.info("テスト実行を開始します", tests_count=suite.countTestCases())

    if use_parallel:
        result = run_tests_in_parallel(suite, max_workers)
        if json_logger:
            json_logger.info("並列実行でテストケースを実行しました", test_count=len(list(suite)))
    else:
        runner = unittest.TextTestRunner(verbosity=verbosity, buffer=True)
        result = runner.run(suite)

    # パフォーマンス監視の結果を記録
    if monitor:
        monitor.record_test_result(result.wasSuccessful())

    # 自己適応監視のチェック
    if self_adapting_monitor:
        violations = self_adapting_monitor.check_thresholds(monitor.metrics if monitor else PerformanceMetrics())
        if violations:
            self_adapting_monitor.generate_alert(violations, monitor.metrics if monitor else PerformanceMetrics())
            self_adapting_monitor.adapt_thresholds(monitor.metrics if monitor else PerformanceMetrics(), violations)

    # ロールバックマネージャーの処理
    if rollback_manager:
        if rollback_manager.should_create_backup(result):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_file = rollback_manager.create_backup(result, timestamp)
            if backup_file:
                rollback_manager.cleanup_old_backups()

        if rollback_manager.should_rollback(result):
            # 最新のバックアップにロールバック
            backups = rollback_manager.list_backups()
            if backups:
                if rollback_manager.rollback_to_backup(backups[0]["file"]):
                    if json_logger:
                        json_logger.warning("エラー発生のためバックアップにロールバックしました", backup_file=backups[0]["file"])

    if result.wasSuccessful():
        if json_logger:
            json_logger.info("すべてのテストが成功しました", passed_count=result.testsRun)
        print("\n✅ すべてのテストが成功しました。")
        return 0, result

    if json_logger:
        json_logger.error("テスト実行で失敗が発生しました", failures_count=len(result.failures), errors_count=len(result.errors))

    print(
        f"\n❌ {len(result.failures)}個の失敗、"
        f"{len(result.errors)}個のエラーがあります。"
    )
    return 1, result


    # JSONログを有効にする
    json_logger = None
    if context.config.enable_json_logging:
        log_path = context.config.json_log_path or (PROJECT_ROOT / "test_run.json")
        json_logger = JsonLogger(log_path)

    # パフォーマンス監視を有効にする
    metrics = PerformanceMetrics()
    monitor = PerformanceMonitor(metrics) if context.config.enable_performance_metrics else None

    # 自己適応監視を有効にする
    self_adapting_monitor = None
    if context.config.enable_self_adapting_thresholds:
        self_adapting_monitor = SelfAdaptingMonitor(context.config, json_logger)
        self_adapting_monitor.start_monitoring()

    # ロールバックマネージャーを有効にする
    rollback_manager = None
    if context.config.enable_rollback_automation:
        rollback_manager = TestRollbackManager(context.config, json_logger)

    if monitor:
        monitor.start_monitoring()

    try:
        result_code, test_result = run_suite(suite, verbosity=context.effective_verbosity, monitor=monitor, use_parallel=context.config.enable_parallel_execution, max_workers=context.config.max_parallel_workers, json_logger=json_logger, self_adapting_monitor=self_adapting_monitor, rollback_manager=rollback_manager)
        return result_code
    finally:
        if monitor:
            monitor.stop_monitoring()
            # パフォーマンスレポートを保存
            if context.config.performance_report_path:
                save_performance_report(metrics, context.config.performance_report_path)
                if json_logger:
                    json_logger.info("パフォーマンスレポートを保存しました", report_path=str(context.config.performance_report_path))
            else:
                # デフォルトのパフォーマンスレポートパスを使用
                default_report_path = PROJECT_ROOT / "performance_report.json"
                save_performance_report(metrics, default_report_path)
                if json_logger:
                    json_logger.info("パフォーマンスレポートを保存しました", report_path=str(default_report_path))

                # コンソールにもパフォーマンス情報を表示
                print("\n=== パフォーマンスサマリー ===")
                print(f"実行時間: {metrics.total_time:.2f}秒")
                print(f"平均CPU使用率: {metrics.average_cpu:.1f}%")
                print(f"最大メモリ使用量: {metrics.max_memory:.1f}MB")
                print(f"テストケース数: {metrics.total_tests}")
                print(f"成功: {metrics.passed_tests}, 失敗: {metrics.failed_tests}")

        if json_logger:
            json_logger.close()

        return result_code
def normalize_module_name(name: str) -> str:
    candidate = name.strip()
    if not candidate:
        raise TestRunnerError(
            "テストモジュール名に空文字は指定できません / "
            "Test module names must not be empty"
        )
    if candidate.endswith(".py"):
        candidate = candidate[:-3]
    if candidate.startswith("tests."):
        candidate = candidate.split(".", maxsplit=1)[1]
    if candidate.startswith(".") or candidate.endswith("."):
        raise TestRunnerError(
            "テストモジュール名が無効です: "
            f"{name}\nInvalid test module name: {name}"
        )
    if any(sep in candidate for sep in ("/", "\\")):
        raise TestRunnerError(
            "テストモジュール名にパス区切りは使用できません: "
            f"{name}\nTest module names must not contain path separators: {name}"
        )
    return candidate


def resolve_module_names(config: RunnerConfig, names: Iterable[str]) -> list[str]:
    """テストモジュール名を正規化し、存在確認する。"""
    available = set(list_tests(config))
    resolved = []
    missing = []
    invalid_messages: list[str] = []
    seen: set[str] = set()
    for name in names:
        try:
            module = normalize_module_name(name)
        except TestRunnerError as exc:
            invalid_messages.append(str(exc))
            continue
        if module in seen:
            invalid_messages.append(
                "テストモジュール名が重複しています: "
                f"{module}\nDuplicated test module name: {module}"
            )
            continue
        seen.add(module)
        if module not in available:
            missing.append(module)
        else:
            resolved.append(module)

    if invalid_messages:
        raise TestRunnerError("\n".join(invalid_messages))
    if missing:
        message_lines = [
            "指定されたテストモジュールが見つかりません: " + ", ".join(sorted(missing)),
            "Missing test modules: " + ", ".join(sorted(missing)),
        ]
        if available:
            available_list = ", ".join(sorted(available))
            message_lines.extend(
                [
                    "利用可能なテストモジュール: " + available_list,
                    "Available test modules: " + available_list,
                ]
            )
        raise TestRunnerError("\n".join(message_lines))

def create_config_template(_: argparse.Namespace, context: CommandContext) -> int:
    """設定テンプレートを作成する。"""
    template_path = PROJECT_ROOT / "config" / "test_runner_template.json"
    try:
        with template_path.open("w", encoding="utf-8") as f:
            json.dump({
                "tests_dir": "tests",
                "default_pattern": "test_*.py",
                "default_verbosity": 2,
                "extra_python_paths": [],
                "show_traceback": False,
                "enable_performance_metrics": False,
                "performance_report_path": None,
                "enable_parallel_execution": False,
                "max_parallel_workers": 4,
            }, f, indent=2, ensure_ascii=False)
        print(f"設定テンプレートを作成しました: {template_path}")
        print("このファイルを config/test_runner.json にコピーしてカスタマイズしてください。")
        return 0
    except OSError as e:
        raise TestRunnerError(f"テンプレートの作成に失敗しました: {e}")


def run_selected_tests(args: argparse.Namespace, context: CommandContext) -> int:
    modules = resolve_module_names(context.config, args.tests)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for module_name in modules:
        try:
            module = importlib.import_module(f"{config_tests_package_name(context.config)}.{module_name}")
        except ModuleNotFoundError as exc:
            raise TestRunnerError(
                "テストモジュールを読み込めません: "
                f"{module_name}\nUnable to import test module: "
                f"{module_name}"
            ) from exc
        suite.addTests(loader.loadTestsFromModule(module))
    if suite.countTestCases() == 0:
        raise TestRunnerError(
            "有効なテストケースが検出されませんでした / "
            "No test cases were discovered"
        )
    return run_suite(suite, verbosity=context.effective_verbosity, use_parallel=context.config.enable_parallel_execution, max_workers=context.config.max_parallel_workers)


def show_available_tests(_: argparse.Namespace, context: CommandContext) -> int:
    modules = list_tests(context.config)
    if not modules:
        raise TestRunnerError(
            "テストが見つかりませんでした。`tests/` を確認してください / "
            "No tests were found. Please check the `tests/` directory"
        )
    print("利用可能なテストモジュール:")
    for module in modules:
        print(f" - {module}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="""
        Cocoaテストランナー - 包括的なテスト実行ツール

        使用例:
          python run_tests.py all                           # すべてのテストを実行
          python run_tests.py run test_cocoa               # 特定のテストを実行
          python run_tests.py list                         # 利用可能なテストを表示
          python run_tests.py template                     # 設定テンプレートを作成

          python run_tests.py all --performance --parallel --workers 8  # パフォーマンス監視と並列実行を有効化
          python run_tests.py all --pattern "*integration*"             # パターンでテストをフィルタ
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.set_defaults(handler=None)

    parser.add_argument(
        "--verbosity",
        type=validate_verbosity,
        default=None,
        help="""
        unittestの冗長度レベル (既定: 設定ファイルまたは2)
        0: 静寂モード
        1: テスト結果のみ
        2: 詳細なテスト結果 (推奨)
        """,
    )

    parser.add_argument(
        "--config",
        default=None,
        help="""
        テストランナー設定ファイルへのパス (既定: config/test_runner.json)
        設定テンプレートは 'python run_tests.py template' で作成できます。
        """,
    )

    parser.add_argument(
        "--performance",
        action="store_true",
        help="""
        パフォーマンス監視を有効にします。
        CPU使用率、メモリ使用量、実行時間を計測し、レポートを生成します。
        """,
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        help="""
        並列実行を有効にします。
        複数のテストケースを同時に実行して実行時間を短縮します。
        """,
    )

    parser.add_argument(
        "--adaptive",
        action="store_true",
        help="""
        自己適応監視を有効にします。
        パフォーマンスしきい値を自動的に調整し、システムに適応します。
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="利用可能なコマンド")

    all_parser = subparsers.add_parser(
        "all",
        help="すべてのテストを実行する",
        description="""
        すべてのテストケースを実行します。

        使用例:
          python run_tests.py all
          python run_tests.py all --pattern "*test*"
          python run_tests.py all --performance --parallel
        """,
    )
    all_parser.add_argument(
        "--pattern",
        type=validate_pattern,
        default=None,
        help="""
        テストファイルのglobパターン (既定: 設定ファイルの値)
        例: "*test*", "test_*.py", "*integration*"
        """,
    )
    all_parser.set_defaults(handler=run_all_tests)

    run_parser = subparsers.add_parser(
        "run",
        help="特定のテストモジュールを実行する",
        description="""
        指定されたテストモジュールのみを実行します。

        使用例:
          python run_tests.py run test_cocoa
          python run_tests.py run test_cocoa test_utils
        """,
    )
    run_parser.add_argument(
        "tests",
        nargs="+",
        help="""
        実行するテストモジュール名 (例: test_cocoa)
        拡張子(.py)は不要です。
        """,
    )
    run_parser.set_defaults(handler=run_selected_tests)

    list_parser = subparsers.add_parser(
        "list",
        help="利用可能なテストモジュールを表示する",
        description="""
        利用可能なテストモジュールの一覧を表示します。

        使用例:
          python run_tests.py list
        """,
    )
    list_parser.set_defaults(handler=show_available_tests)

    template_parser = subparsers.add_parser(
        "template",
        help="設定テンプレートを作成する",
        description="""
        テストランナーの設定テンプレートを作成します。

        使用例:
          python run_tests.py template
        """,
    )
    template_parser.set_defaults(handler=create_config_template)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ensure_pythonpath()

    if args.handler is None:
        parser.print_help()
        return 1

    config_path = resolve_config_path(args.config)
    config_manager = ConfigManager(config_path)
    try:
        config = config_manager.ensure_latest()
    except TestRunnerError as exc:
        print(str(exc))
        return 1

    # CLI引数でパフォーマンス設定を上書き
    if args.performance:
        config = RunnerConfig(
            tests_dir=config.tests_dir,
            default_pattern=config.default_pattern,
            default_verbosity=config.default_verbosity,
            extra_python_paths=config.extra_python_paths,
            show_traceback=config.show_traceback,
            enable_performance_metrics=True,
            performance_report_path=Path(args.performance_report) if args.performance_report else None,
            enable_parallel_execution=config.enable_parallel_execution,
            max_parallel_workers=config.max_parallel_workers,
        )

    # CLI引数で並列実行設定を上書き
    if args.parallel:
        config = RunnerConfig(
            tests_dir=config.tests_dir,
            default_pattern=config.default_pattern,
            default_verbosity=config.default_verbosity,
            extra_python_paths=config.extra_python_paths,
            show_traceback=config.show_traceback,
            enable_performance_metrics=config.enable_performance_metrics,
            performance_report_path=config.performance_report_path,
            enable_parallel_execution=True,
            max_parallel_workers=args.workers,
            enable_self_adapting_thresholds=config.enable_self_adapting_thresholds,
            monitoring_thresholds=config.monitoring_thresholds,
        )

    # CLI引数で自己適応監視設定を上書き
    if args.adaptive:
        config = RunnerConfig(
            tests_dir=config.tests_dir,
            default_pattern=config.default_pattern,
            default_verbosity=config.default_verbosity,
            extra_python_paths=config.extra_python_paths,
            show_traceback=config.show_traceback,
            enable_performance_metrics=config.enable_performance_metrics,
            performance_report_path=config.performance_report_path,
            enable_parallel_execution=config.enable_parallel_execution,
            max_parallel_workers=config.max_parallel_workers,
            enable_self_adapting_thresholds=True,
            monitoring_thresholds=config.monitoring_thresholds,
        )

    ensure_pythonpath(config.extra_python_paths)
    context = CommandContext(parser=parser, config=config, args=args)
    return run_with_exception_handling(args.handler, args, context)


def resolve_project_path(value: Any) -> Path:
    if isinstance(value, Path):
        path = value
    elif isinstance(value, str):
        path = Path(value).expanduser()
    else:
        raise TestRunnerError(
            "パス設定には文字列を使用してください / "
            "Path configuration values must be strings"
        )
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def load_runner_config(path: Path) -> RunnerConfig:
    defaults = {
        "tests_dir": str(DEFAULT_TESTS_DIR),
        "default_pattern": DEFAULT_PATTERN,
        "default_verbosity": DEFAULT_VERBOSITY,
        "extra_python_paths": [],
        "show_traceback": False,
        "enable_performance_metrics": False,
        "performance_report_path": None,
        "enable_parallel_execution": False,
        "max_parallel_workers": 4,
        "enable_self_adapting_thresholds": False,
        "monitoring_thresholds": {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "execution_time_per_test": 30.0,
            "error_rate": 10.0,
        },
    }
    if not path.exists():
        return build_runner_config(defaults)
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except json.JSONDecodeError as exc:
        raise TestRunnerError(
            "設定ファイルの読み込みに失敗しました: "
            f"{path}\nFailed to parse configuration file: {path}"
        ) from exc
    except OSError as exc:
        raise TestRunnerError(
            "設定ファイルを読み込めません: "
            f"{path}\nUnable to read configuration file: {path}"
        ) from exc

    if not isinstance(raw, dict):
        raise TestRunnerError(
            "設定ファイルの形式が不正です / "
            "The configuration file must contain a JSON object"
        )

    merged: dict[str, Any] = {**defaults, **raw}
    return build_runner_config(merged)


def build_runner_config(data: dict[str, Any]) -> RunnerConfig:
    tests_dir = resolve_project_path(data.get("tests_dir"))
    if not tests_dir.exists():
        raise TestRunnerError(
            "テストディレクトリが存在しません: "
            f"{tests_dir}\nThe tests directory does not exist: {tests_dir}"
        )

    try:
        default_pattern = validate_pattern(str(data.get("default_pattern", DEFAULT_PATTERN)))
    except argparse.ArgumentTypeError as exc:
        raise TestRunnerError(
            "`default_pattern` が不正です / Invalid value for `default_pattern`"
        ) from exc

    default_verbosity = validate_config_verbosity(data.get("default_verbosity", DEFAULT_VERBOSITY))

    extra_python_paths_field = data.get("extra_python_paths", [])
    if not isinstance(extra_python_paths_field, list):
        raise TestRunnerError(
            "`extra_python_paths` は文字列の配列で指定してください / "
            "`extra_python_paths` must be a list of paths"
        )

    extra_python_paths: list[Path] = []
    for entry in extra_python_paths_field:
        path = resolve_project_path(entry)
        if not path.exists():
            raise TestRunnerError(
                "追加Pythonパスが存在しません: "
                f"{path}\nThe extra Python path does not exist: {path}"
            )
        if path not in extra_python_paths:
            extra_python_paths.append(path)

    show_traceback = data.get("show_traceback", False)
    if not isinstance(show_traceback, bool):
        raise TestRunnerError(
            "`show_traceback` は真偽値で指定してください / "
            "`show_traceback` must be a boolean"
        )

    enable_performance_metrics = data.get("enable_performance_metrics", False)
    if not isinstance(enable_performance_metrics, bool):
        raise TestRunnerError(
            "`enable_performance_metrics` は真偽値で指定してください / "
            "`enable_performance_metrics` must be a boolean"
        )

    performance_report_path = data.get("performance_report_path")
    if performance_report_path is not None:
        if not isinstance(performance_report_path, str):
            raise TestRunnerError(
                "`performance_report_path` は文字列で指定してください / "
                "`performance_report_path` must be a string"
            )
        performance_report_path = resolve_project_path(performance_report_path)
    else:
        performance_report_path = None

    enable_parallel_execution = data.get("enable_parallel_execution", False)
    if not isinstance(enable_parallel_execution, bool):
        raise TestRunnerError(
            "`enable_parallel_execution` は真偽値で指定してください / "
            "`enable_parallel_execution` must be a boolean"
        )

    max_parallel_workers = data.get("max_parallel_workers", 4)
    if not isinstance(max_parallel_workers, int) or max_parallel_workers < 1:
        raise TestRunnerError(
            "`max_parallel_workers` は1以上の整数で指定してください / "
            "`max_parallel_workers` must be an integer greater than or equal to 1"
        )

    enable_self_adapting_thresholds = data.get("enable_self_adapting_thresholds", False)
    if not isinstance(enable_self_adapting_thresholds, bool):
        raise TestRunnerError(
            "`enable_self_adapting_thresholds` は真偽値で指定してください / "
            "`enable_self_adapting_thresholds` must be a boolean"
        )

    monitoring_thresholds = data.get("monitoring_thresholds", {
        "cpu_percent": 80.0,
        "memory_percent": 85.0,
        "execution_time_per_test": 30.0,
        "error_rate": 10.0,
    })
    if not isinstance(monitoring_thresholds, dict):
        raise TestRunnerError(
            "`monitoring_thresholds` はオブジェクトで指定してください / "
            "`monitoring_thresholds` must be an object"
        )

    # しきい値の検証
    required_thresholds = ["cpu_percent", "memory_percent", "execution_time_per_test", "error_rate"]
    for threshold_name in required_thresholds:
        if threshold_name not in monitoring_thresholds:
            raise TestRunnerError(
                f"`monitoring_thresholds` に `{threshold_name}` が設定されていません / "
                f"`{threshold_name}` is missing from `monitoring_thresholds`"
            )
        threshold_value = monitoring_thresholds[threshold_name]
        if not isinstance(threshold_value, (int, float)) or threshold_value <= 0:
            raise TestRunnerError(
                f"`monitoring_thresholds.{threshold_name}` は正の数で指定してください / "
                f"`monitoring_thresholds.{threshold_name}` must be a positive number"
            )

    return RunnerConfig(
        tests_dir=tests_dir,
        default_pattern=default_pattern,
        default_verbosity=default_verbosity,
        extra_python_paths=tuple(extra_python_paths),
        show_traceback=show_traceback,
        enable_performance_metrics=enable_performance_metrics,
        performance_report_path=performance_report_path,
        enable_parallel_execution=enable_parallel_execution,
        max_parallel_workers=max_parallel_workers,
        enable_self_adapting_thresholds=enable_self_adapting_thresholds,
        monitoring_thresholds=monitoring_thresholds,
    )


def resolve_project_path(value: Any) -> Path:
    if isinstance(value, Path):
        path = value
    elif isinstance(value, str):
        path = Path(value).expanduser()
    else:
        raise TestRunnerError(
            "パス設定には文字列を使用してください / "
            "Path configuration values must be strings"
        )
    if not path.is_absolute():
        path = PROJECT_ROOT / path
@dataclass
class PerformanceMetrics:
    """テスト実行のパフォーマンス指標を記録する。"""
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    cpu_percentages: list[float] = field(default_factory=list)
    memory_usage: list[float] = field(default_factory=list)
    test_case_times: dict[str, float] = field(default_factory=dict)
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0

    @property
    def total_time(self) -> float:
        return self.end_time - self.start_time

    @property
    def average_cpu(self) -> float:
        return sum(self.cpu_percentages) / len(self.cpu_percentages) if self.cpu_percentages else 0.0

    @property
    def max_memory(self) -> float:
        return max(self.memory_usage) if self.memory_usage else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_time": self.total_time,
            "average_cpu_percent": self.average_cpu,
            "max_memory_mb": self.max_memory,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "test_case_times": self.test_case_times,
        }


class PerformanceMonitor:
    """テスト実行中のパフォーマンスを監視する。"""

    def __init__(self, metrics: PerformanceMetrics):
        self.metrics = metrics
        self._process = psutil.Process()
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None

    def start_monitoring(self) -> None:
        """パフォーマンス監視を開始する。"""
        if self._monitoring:
            return
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor, daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """パフォーマンス監視を停止する。"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        self.metrics.end_time = time.time()

    def _monitor(self) -> None:
        """監視スレッドで実行される監視処理。"""
        while self._monitoring:
            try:
                cpu_percent = self._process.cpu_percent()
                memory_info = self._process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024

                self.metrics.cpu_percentages.append(cpu_percent)
                self.metrics.memory_usage.append(memory_mb)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            time.sleep(0.1)  # 100ms間隔で監視

    def record_test_case(self, test_name: str, duration: float) -> None:
        """テストケースの実行時間を記録する。"""
        self.metrics.test_case_times[test_name] = duration

    def record_test_result(self, passed: bool) -> None:
        """テスト結果を記録する。"""
        self.metrics.total_tests += 1
        if passed:
            self.metrics.passed_tests += 1
        else:
            self.metrics.failed_tests += 1


def save_performance_report(metrics: PerformanceMetrics, path: Path) -> None:
    """パフォーマンスレポートをJSONファイルに保存する。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(metrics.to_dict(), f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"パフォーマンスレポートの保存に失敗しました: {e}")


def run_with_exception_handling(
    handler: Callable[[argparse.Namespace, CommandContext], int],
    args: argparse.Namespace,
    context: CommandContext,
) -> int:
    try:
        return handler(args, context)
    except TestRunnerError as exc:
        print(str(exc))
        return 1
    except KeyboardInterrupt:
        print(
            "テスト実行はユーザーによって中断されました / "
            "Test execution was interrupted by the user"
        )
        return 1
    except Exception:
        if context.config.show_traceback:
            traceback.print_exc()
        else:
            print(
                "予期しないエラーが発生しました。詳細は `config/test_runner.json` の "
                "`show_traceback` を true に設定すると表示できます。\n"
                "An unexpected error occurred. Set `show_traceback` to true in "
                "`config/test_runner.json` to display details."
            )
        return 1


if __name__ == "__main__":
    sys.exit(main())
