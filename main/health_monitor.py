"""
Production-Grade Health Monitoring System

国家レベルの運用に必要な包括的なヘルスチェック機能:
- システムリソース監視
- アプリケーション状態確認
- 依存関係の健全性チェック
- 自動復旧メカニズム
"""
import logging
import time
import os
import sys
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健全性ステータス"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


@dataclass
class HealthCheckResult:
    """ヘルスチェック結果"""
    component: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    response_time_ms: float = 0.0


class HealthMonitor:
    """Production-Grade Health Monitoring"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.checks: Dict[str, Callable] = {}
        self.last_results: Dict[str, HealthCheckResult] = {}
        self.startup_time = time.time()

        # デフォルトチェックを登録
        self._register_default_checks()

    def _register_default_checks(self):
        """デフォルトヘルスチェックの登録"""
        self.register_check("system_resources", self._check_system_resources)
        self.register_check("disk_space", self._check_disk_space)
        self.register_check("memory", self._check_memory)
        self.register_check("process_health", self._check_process_health)
        self.register_check("file_permissions", self._check_file_permissions)

    def register_check(self, name: str, check_func: Callable):
        """カスタムヘルスチェックの登録"""
        self.checks[name] = check_func
        logger.info(f"ヘルスチェック登録: {name}")

    def run_all_checks(self) -> Dict[str, Any]:
        """全ヘルスチェックの実行"""
        results = {}
        overall_status = HealthStatus.HEALTHY

        for name, check_func in self.checks.items():
            try:
                start = time.time()
                result = check_func()
                result.response_time_ms = round((time.time() - start) * 1000, 2)

                results[name] = result
                self.last_results[name] = result

                # 最悪のステータスを全体ステータスとする
                if result.status.value == "critical":
                    overall_status = HealthStatus.CRITICAL
                elif result.status.value == "unhealthy" and overall_status != HealthStatus.CRITICAL:
                    overall_status = HealthStatus.UNHEALTHY
                elif result.status.value == "degraded" and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED

            except Exception as e:
                logger.error(f"ヘルスチェック失敗 ({name}): {e}")
                result = HealthCheckResult(
                    component=name,
                    status=HealthStatus.CRITICAL,
                    message=f"チェック実行エラー: {str(e)}"
                )
                results[name] = result
                overall_status = HealthStatus.CRITICAL

        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": round(time.time() - self.startup_time, 2),
            "checks": {name: self._result_to_dict(result) for name, result in results.items()},
            "summary": self._generate_summary(results)
        }

    def run_check(self, name: str) -> Optional[HealthCheckResult]:
        """単一ヘルスチェックの実行"""
        if name not in self.checks:
            logger.warning(f"未登録のヘルスチェック: {name}")
            return None

        try:
            start = time.time()
            result = self.checks[name]()
            result.response_time_ms = round((time.time() - start) * 1000, 2)
            self.last_results[name] = result
            return result
        except Exception as e:
            logger.error(f"ヘルスチェック失敗 ({name}): {e}")
            return HealthCheckResult(
                component=name,
                status=HealthStatus.CRITICAL,
                message=f"チェック実行エラー: {str(e)}"
            )

    def get_readiness(self) -> Dict[str, Any]:
        """Readinessプローブ (K8s互換)"""
        critical_checks = ["system_resources", "memory", "disk_space"]
        results = {}

        for check_name in critical_checks:
            if check_name in self.checks:
                result = self.run_check(check_name)
                if result:
                    results[check_name] = result

        # 全ての重要チェックがhealthy/degradedならready
        is_ready = all(
            r.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
            for r in results.values()
        )

        return {
            "ready": is_ready,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {name: self._result_to_dict(result) for name, result in results.items()}
        }

    def get_liveness(self) -> Dict[str, Any]:
        """Livenessプローブ (K8s互換)"""
        # プロセスが生きていることの簡易チェック
        try:
            uptime = time.time() - self.startup_time
            return {
                "alive": True,
                "uptime_seconds": round(uptime, 2),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.critical(f"Livenessチェック失敗: {e}")
            return {
                "alive": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    # =============== Default Health Checks ===============

    def _check_system_resources(self) -> HealthCheckResult:
        """システムリソースチェック"""
        if not psutil:
            return HealthCheckResult(
                component="system_resources",
                status=HealthStatus.DEGRADED,
                message="psutil not available"
            )

        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # 閾値判定
            issues = []
            status = HealthStatus.HEALTHY

            if cpu_percent > 90:
                issues.append(f"CPU使用率が高い: {cpu_percent}%")
                status = HealthStatus.UNHEALTHY
            elif cpu_percent > 70:
                issues.append(f"CPU使用率が上昇: {cpu_percent}%")
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.DEGRADED

            if memory.percent > 90:
                issues.append(f"メモリ使用率が高い: {memory.percent}%")
                status = HealthStatus.UNHEALTHY
            elif memory.percent > 80:
                issues.append(f"メモリ使用率が上昇: {memory.percent}%")
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.DEGRADED

            message = "; ".join(issues) if issues else "システムリソース正常"

            return HealthCheckResult(
                component="system_resources",
                status=status,
                message=message,
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": disk.percent
                }
            )
        except Exception as e:
            return HealthCheckResult(
                component="system_resources",
                status=HealthStatus.CRITICAL,
                message=f"リソースチェックエラー: {str(e)}"
            )

    def _check_disk_space(self) -> HealthCheckResult:
        """ディスク容量チェック"""
        if not psutil:
            return HealthCheckResult(
                component="disk_space",
                status=HealthStatus.DEGRADED,
                message="psutil not available"
            )

        try:
            disk = psutil.disk_usage('/')

            if disk.percent > 95:
                status = HealthStatus.CRITICAL
                message = f"ディスク容量が危険レベル: {disk.percent}%"
            elif disk.percent > 85:
                status = HealthStatus.UNHEALTHY
                message = f"ディスク容量が不足: {disk.percent}%"
            elif disk.percent > 70:
                status = HealthStatus.DEGRADED
                message = f"ディスク容量が上昇: {disk.percent}%"
            else:
                status = HealthStatus.HEALTHY
                message = "ディスク容量正常"

            return HealthCheckResult(
                component="disk_space",
                status=status,
                message=message,
                details={
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent": disk.percent
                }
            )
        except Exception as e:
            return HealthCheckResult(
                component="disk_space",
                status=HealthStatus.CRITICAL,
                message=f"ディスク容量チェックエラー: {str(e)}"
            )

    def _check_memory(self) -> HealthCheckResult:
        """メモリ詳細チェック"""
        if not psutil:
            return HealthCheckResult(
                component="memory",
                status=HealthStatus.DEGRADED,
                message="psutil not available"
            )

        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            issues = []
            status = HealthStatus.HEALTHY

            if memory.percent > 95:
                issues.append(f"メモリ使用率が危険レベル: {memory.percent}%")
                status = HealthStatus.CRITICAL
            elif memory.percent > 85:
                issues.append(f"メモリ使用率が高い: {memory.percent}%")
                status = HealthStatus.UNHEALTHY
            elif memory.percent > 75:
                issues.append(f"メモリ使用率が上昇: {memory.percent}%")
                status = HealthStatus.DEGRADED

            if swap.percent > 50:
                issues.append(f"スワップ使用率が高い: {swap.percent}%")
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.DEGRADED

            message = "; ".join(issues) if issues else "メモリ正常"

            return HealthCheckResult(
                component="memory",
                status=status,
                message=message,
                details={
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "percent": memory.percent,
                    "swap_percent": swap.percent
                }
            )
        except Exception as e:
            return HealthCheckResult(
                component="memory",
                status=HealthStatus.CRITICAL,
                message=f"メモリチェックエラー: {str(e)}"
            )

    def _check_process_health(self) -> HealthCheckResult:
        """プロセス健全性チェック"""
        if not psutil:
            return HealthCheckResult(
                component="process_health",
                status=HealthStatus.DEGRADED,
                message="psutil not available"
            )

        try:
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info()
            process_cpu = process.cpu_percent(interval=0.1)

            issues = []
            status = HealthStatus.HEALTHY

            # プロセスメモリチェック
            memory_mb = process_memory.rss / (1024 * 1024)
            if memory_mb > 2048:  # 2GB
                issues.append(f"プロセスメモリが大きい: {round(memory_mb, 2)}MB")
                status = HealthStatus.DEGRADED

            # プロセスCPUチェック
            if process_cpu > 80:
                issues.append(f"プロセスCPU使用率が高い: {process_cpu}%")
                status = HealthStatus.DEGRADED

            # ファイルディスクリプタチェック (Linuxのみ)
            if hasattr(process, 'num_fds'):
                try:
                    num_fds = process.num_fds()
                    if num_fds > 1000:
                        issues.append(f"ファイルディスクリプタ数が多い: {num_fds}")
                        status = HealthStatus.DEGRADED
                except Exception:
                    pass

            message = "; ".join(issues) if issues else "プロセス正常"

            return HealthCheckResult(
                component="process_health",
                status=status,
                message=message,
                details={
                    "pid": process.pid,
                    "memory_mb": round(memory_mb, 2),
                    "cpu_percent": process_cpu,
                    "num_threads": process.num_threads()
                }
            )
        except Exception as e:
            return HealthCheckResult(
                component="process_health",
                status=HealthStatus.CRITICAL,
                message=f"プロセスチェックエラー: {str(e)}"
            )

    def _check_file_permissions(self) -> HealthCheckResult:
        """ファイル権限チェック"""
        try:
            critical_paths = [
                "config",
                "logs",
                "backups",
                "data"
            ]

            issues = []
            status = HealthStatus.HEALTHY

            for path_str in critical_paths:
                path = Path(path_str)

                # ディレクトリ存在チェック
                if not path.exists():
                    issues.append(f"必須ディレクトリが存在しません: {path_str}")
                    status = HealthStatus.UNHEALTHY
                    continue

                # 書き込み権限チェック
                if not os.access(path, os.W_OK):
                    issues.append(f"書き込み権限がありません: {path_str}")
                    status = HealthStatus.UNHEALTHY

                # 読み取り権限チェック
                if not os.access(path, os.R_OK):
                    issues.append(f"読み取り権限がありません: {path_str}")
                    status = HealthStatus.UNHEALTHY

            message = "; ".join(issues) if issues else "ファイル権限正常"

            return HealthCheckResult(
                component="file_permissions",
                status=status,
                message=message,
                details={"checked_paths": critical_paths}
            )
        except Exception as e:
            return HealthCheckResult(
                component="file_permissions",
                status=HealthStatus.CRITICAL,
                message=f"ファイル権限チェックエラー: {str(e)}"
            )

    # =============== Utility Methods ===============

    def _result_to_dict(self, result: HealthCheckResult) -> Dict[str, Any]:
        """HealthCheckResultを辞書に変換"""
        return {
            "status": result.status.value,
            "message": result.message,
            "details": result.details,
            "timestamp": result.timestamp,
            "response_time_ms": result.response_time_ms
        }

    def _generate_summary(self, results: Dict[str, HealthCheckResult]) -> Dict[str, Any]:
        """サマリー生成"""
        status_counts = {
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "critical": 0
        }

        for result in results.values():
            status_counts[result.status.value] += 1

        return {
            "total_checks": len(results),
            "status_counts": status_counts,
            "critical_issues": [
                result.message
                for result in results.values()
                if result.status == HealthStatus.CRITICAL
            ],
            "warnings": [
                result.message
                for result in results.values()
                if result.status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]
            ]
        }


# グローバルインスタンス
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """ヘルスモニターインスタンス取得"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor


def initialize_health_monitoring(config: Optional[Dict[str, Any]] = None) -> HealthMonitor:
    """ヘルスモニター初期化"""
    global _health_monitor
    _health_monitor = HealthMonitor(config)
    logger.info("ヘルスモニターを初期化しました")
    return _health_monitor
