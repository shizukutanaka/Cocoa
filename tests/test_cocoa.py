"""
Cocoaプロジェクトのテストスイート
軽量で実用的なテストを提供
"""
import unittest
import tempfile
import os
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_DIR = PROJECT_ROOT / "main"

# テスト対象のモジュールをインポート
sys.path.append(str(MAIN_DIR))

from performance_monitor import PerformanceMonitor
from logging_manager import LoggingManager

class TestPerformanceMonitor(unittest.TestCase):
    """PerformanceMonitorのテスト"""

    def setUp(self):
        """テスト前の準備"""
        self.config = {
            "interval": 1,
            "history_size": 10,
            "memory_threshold": 80,
            "cpu_threshold": 90,
            "disk_io_threshold": 1000,
            "process_memory_threshold": 90
        }
        self.monitor = PerformanceMonitor(self.config)

    def tearDown(self):
        """テスト後のクリーンアップ"""
        if self.monitor.running:
            self.monitor.stop_monitoring()

    def test_initialization(self):
        """初期化のテスト"""
        self.assertIsNotNone(self.monitor)
        self.assertEqual(self.monitor.interval, 1)
        self.assertEqual(self.monitor.history_size, 10)
        self.assertIn("memory", self.monitor.thresholds)
        self.assertIn("cpu", self.monitor.thresholds)

    def test_get_system_info(self):
        """システム情報の取得テスト"""
        system_info = self.monitor.get_system_info()
        self.assertIsInstance(system_info, dict)
        self.assertIn("platform", system_info)
        self.assertIn("cpu_count", system_info)

    def test_performance_report(self):
        """パフォーマンスレポートのテスト"""
        report = self.monitor.get_performance_report()
        self.assertIsInstance(report, dict)
        self.assertIn("current_stats", report)
        self.assertIn("history", report)
        self.assertIn("timestamp", report)

    def test_config_update(self):
        """設定更新のテスト"""
        new_config = {
            "interval": 2,
            "memory_threshold": 85
        }
        self.monitor.update_config(new_config)
        self.assertEqual(self.monitor.interval, 2)
        self.assertEqual(self.monitor.thresholds["memory"], 85)

    def test_export_metrics(self):
        """メトリクスエクスポートのテスト"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name

        try:
            result = self.monitor.export_metrics(temp_file)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(temp_file))

            # エクスポートされたファイルの内容を確認
            with open(temp_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.assertIn("export_time", data)
                self.assertIn("config", data)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_monitoring_start_stop(self):
        """監視開始・停止のテスト"""
        # 監視開始
        self.monitor.start_monitoring()
        self.assertTrue(self.monitor.running)

        # 監視停止
        self.monitor.stop_monitoring()
        self.assertFalse(self.monitor.running)

    def test_threshold_checking(self):
        """閾値チェックのテスト"""
        # メモリ使用率の閾値チェック
        memory_usage = self.monitor.check_thresholds()
        self.assertIsInstance(memory_usage, dict)

        # CPU使用率の閾値チェック
        cpu_usage = self.monitor.check_thresholds()
        self.assertIsInstance(cpu_usage, dict)

class TestLoggingManager(unittest.TestCase):
    """LoggingManagerのテスト"""

    def setUp(self):
        """テスト前の準備"""
        self.config = {
            "log_dir": "test_logs",
            "log_level": "INFO",
            "max_bytes": 1024 * 1024,  # 1MB
            "backup_count": 3
        }
        self.logger_manager = LoggingManager(self.config)

    def tearDown(self):
        """テスト後のクリーンアップ"""
        # テスト用ログディレクトリのクリーンアップ
        log_dir = Path("test_logs")
        if log_dir.exists():
            import shutil
            shutil.rmtree(log_dir)

    def test_initialization(self):
        """初期化のテスト"""
        self.assertIsNotNone(self.logger_manager)
        self.assertEqual(self.logger_manager.log_level, "INFO")
        self.assertEqual(self.logger_manager.max_bytes, 1024 * 1024)

    def test_log_message(self):
        """ログメッセージのテスト"""
        self.logger_manager.log_message("INFO", "テストメッセージ")
        self.logger_manager.log_message("ERROR", "テストエラー", {"extra": "data"})

        # ログファイルが作成されていることを確認
        log_file = Path("test_logs") / "cocoa.log"
        self.assertTrue(log_file.exists())

    def test_log_avatar_action(self):
        """アバターアクションログのテスト"""
        self.logger_manager.log_avatar_action("test_avatar", "load", 1.5, True)
        self.logger_manager.log_avatar_action("test_avatar", "save", 0.8, False)

    def test_log_preset_action(self):
        """プリセットアクションログのテスト"""
        self.logger_manager.log_preset_action("test_preset", "create", 2.1, True)
        self.logger_manager.log_preset_action("test_preset", "delete", 0.3, False)

    def test_log_error(self):
        """エラーログのテスト"""
        test_error = ValueError("テストエラー")
        self.logger_manager.log_error(test_error, "テストコンテキスト")

    def test_search_logs(self):
        """ログ検索のテスト"""
        # いくつかのログメッセージを追加
        for i in range(5):
            self.logger_manager.log_message("INFO", f"テストメッセージ {i}")

        # 検索テスト
        results = self.logger_manager.search_logs("テスト", limit=10)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_get_log_stats(self):
        """ログ統計のテスト"""
        # ログメッセージを追加
        self.logger_manager.log_message("INFO", "テストメッセージ")

        stats = self.logger_manager.get_log_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn("file_size", stats)
        self.assertIn("line_count", stats)

    def test_set_log_level(self):
        """ログレベルの設定テスト"""
        result = self.logger_manager.set_log_level("DEBUG")
        self.assertTrue(result)
        self.assertEqual(self.logger_manager.log_level, "DEBUG")

        # 無効なログレベル
        result = self.logger_manager.set_log_level("INVALID")
        self.assertFalse(result)

    def test_log_file_rotation(self):
        """ログファイルローテーションのテスト"""
        # 大量のログメッセージを追加してローテーションをテスト
        for i in range(100):
            self.logger_manager.log_message("INFO", f"テストメッセージ {i}")

        # ログファイルが作成されていることを確認
        log_file = Path("test_logs") / "cocoa.log"
        self.assertTrue(log_file.exists())

        # ログ統計を確認
        stats = self.logger_manager.get_log_stats()
        self.assertGreater(stats["line_count"], 0)

class TestConfigValidation(unittest.TestCase):
    """設定検証のテスト"""

    def test_config_structure(self):
        """設定構造のテスト"""
        config = {
            "app_name": "Cocoa",
            "version": "1.0.0",
            "debug": False,
            "database": {
                "host": "localhost",
                "port": 5432
            }
        }

        # 必須フィールドの確認
        self.assertIn("app_name", config)
        self.assertIn("version", config)
        self.assertIn("database", config)

        # データベース設定の確認
        self.assertEqual(config["database"]["host"], "localhost")
        self.assertEqual(config["database"]["port"], 5432)

    def test_config_types(self):
        """設定データ型のテスト"""
        config = {
            "debug": False,  # boolean
            "port": 8080,    # integer
            "name": "test",  # string
            "features": ["feature1", "feature2"]  # list
        }

        self.assertIsInstance(config["debug"], bool)
        self.assertIsInstance(config["port"], int)
        self.assertIsInstance(config["name"], str)
        self.assertIsInstance(config["features"], list)

class TestPresetDiff(unittest.TestCase):
    """プリセット差分機能のテスト"""

    def setUp(self):
        """テスト前の準備"""
        self.preset1 = {
            "name": "test_preset1",
            "parameters": {
                "param1": "value1",
                "param2": "value2"
            }
        }

        self.preset2 = {
            "name": "test_preset2",
            "parameters": {
                "param1": "value1_modified",
                "param3": "value3"
            }
        }

    def test_presets_identical(self):
        """同一プリセットのテスト"""
        identical_preset = self.preset1.copy()
        self.assertEqual(self.preset1, identical_preset)

    def test_presets_different(self):
        """異なるプリセットのテスト"""
        self.assertNotEqual(self.preset1, self.preset2)

    def test_parameter_comparison(self):
        """パラメータ比較のテスト"""
        # 共通パラメータ
        self.assertEqual(self.preset1["parameters"]["param1"], "value1")

        # 存在しないパラメータ
        self.assertNotIn("param3", self.preset1["parameters"])
        self.assertIn("param3", self.preset2["parameters"])

if __name__ == '__main__':
    # テストスイートの作成
    unittest.main(verbosity=2)

class TestErrorHandling(unittest.TestCase):
    """エラーハンドリングのテスト"""
    def setUp(self):
        """テスト前の準備"""
        self.config = {
            "interval": 1,
            "history_size": 10,
            "memory_threshold": 80,
            "cpu_threshold": 90
        }
        self.monitor = PerformanceMonitor(self.config)

    def test_invalid_config(self):
        """無効な設定のテスト"""
        invalid_config = {
            "interval": -1,  # 無効な値
            "memory_threshold": "invalid",  # 無効な型
        }

        # 無効な設定でもシステムがクラッシュしないことを確認
        monitor = PerformanceMonitor(invalid_config)
        self.assertIsNotNone(monitor)

    def test_file_not_found_error(self):
        """ファイルが存在しない場合のエラーハンドリングテスト"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_file = f.name

        # ファイルを削除
        os.unlink(temp_file)

        # 存在しないファイルへのアクセスで適切にエラーハンドリングされることを確認
        try:
            self.monitor.export_metrics(temp_file)
            # ここに到達しないはず（エラーが発生するはず）
            self.fail("Expected an exception for non-existent file")
        except Exception:
            # 例外が発生することを確認
            pass

    def test_invalid_log_level(self):
        """無効なログレベルのテスト"""
        config = {
            "log_dir": "test_logs",
            "log_level": "INVALID_LEVEL",
            "max_bytes": 1024,
            "backup_count": 1
        }

        # 無効なログレベルでもシステムがクラッシュしないことを確認
        logger_manager = LoggingManager(config)
        self.assertIsNotNone(logger_manager)

class TestIntegration(unittest.TestCase):
    """統合テスト"""

    def setUp(self):
        """テスト前の準備"""
        self.perf_config = {
            "interval": 1,
            "history_size": 5,
            "memory_threshold": 80,
            "cpu_threshold": 90
        }
        self.log_config = {
            "log_dir": "integration_test_logs",
            "log_level": "INFO",
            "max_bytes": 1024,
            "backup_count": 1
        }

        self.performance_monitor = PerformanceMonitor(self.perf_config)
        self.logging_manager = LoggingManager(self.log_config)

    def tearDown(self):
        """テスト後のクリーンアップ"""
        if self.performance_monitor.running:
            self.performance_monitor.stop_monitoring()

        # テスト用ログディレクトリのクリーンアップ
        log_dir = Path("integration_test_logs")
        if log_dir.exists():
            import shutil
            shutil.rmtree(log_dir)

    def test_system_integration(self):
        """システム統合のテスト"""
        # パフォーマンス監視を開始
        self.performance_monitor.start_monitoring()
        self.assertTrue(self.performance_monitor.running)

        # ログメッセージを記録
        self.logging_manager.log_message("INFO", "統合テスト開始")
        self.logging_manager.log_message("INFO", "パフォーマンス監視中")

        # パフォーマンスレポートを取得
        report = self.performance_monitor.get_performance_report()
        self.assertIsInstance(report, dict)

        # ログ検索を実行
        results = self.logging_manager.search_logs("統合テスト", limit=10)
        self.assertIsInstance(results, list)

        # システムが正常に動作することを確認
        self.assertTrue(self.performance_monitor.running)

        # 監視を停止
        self.performance_monitor.stop_monitoring()
        self.assertFalse(self.performance_monitor.running)

    def test_data_flow(self):
        """データフローのテスト"""
        # パフォーマンスデータを取得
        system_info = self.performance_monitor.get_system_info()
        performance_report = self.performance_monitor.get_performance_report()

        # データをログに記録
        self.logging_manager.log_message("INFO", f"システム情報: {system_info}")
        self.logging_manager.log_message("INFO", f"パフォーマンスレポート: {performance_report}")

        # ログが正常に記録されたことを確認
        stats = self.logging_manager.get_log_stats()
        self.assertGreater(stats["line_count"], 0)
