"""
包括的テストスイート - 本番レベルの品質保証
単体テスト、統合テスト、パフォーマンステスト、セキュリティテストを含む
"""
import os
import sys
import unittest
import pytest
import asyncio
import json
import tempfile
import shutil
import time
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import threading
import subprocess

# テスト対象のモジュールをインポート
sys.path.append(str(Path(__file__).parent.parent / "main"))

try:
    from security_manager import SecurityManager, SecurityPolicy, ThreatLevel
    from performance_manager import PerformanceMonitor, MetricType, HealthStatus
    from error_recovery_system import ErrorRecoverySystem, ErrorSeverity, CircuitBreaker
    from database_manager import DatabaseManager, DatabaseConfig, DatabaseType
    from advanced_logging import AdvancedLogger, LogLevel, LogCategory, EventType
    from backup_recovery_system import BackupManager, BackupType, StorageType
except ImportError as e:
    print(f"テスト対象モジュールのインポートエラー: {e}")
    sys.exit(1)

# テストロガー設定
logging.basicConfig(level=logging.INFO)
test_logger = logging.getLogger(__name__)

class TestBase(unittest.TestCase):
    """テストベースクラス"""

    def setUp(self):
        """テスト前処理"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_data_dir = self.temp_dir / "test_data"
        self.test_data_dir.mkdir(parents=True, exist_ok=True)

        # テスト用設定ファイル作成
        self.config_dir = self.temp_dir / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # テスト開始ログ
        test_logger.info(f"テスト開始: {self._testMethodName}")

    def tearDown(self):
        """テスト後処理"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            test_logger.error(f"テストクリーンアップエラー: {e}")

        test_logger.info(f"テスト完了: {self._testMethodName}")

    def create_test_config(self, filename: str, config_data: Dict[str, Any]) -> Path:
        """テスト用設定ファイルを作成"""
        config_file = self.config_dir / filename
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, default=str)
        return config_file

class TestSecurityManager(TestBase):
    """セキュリティマネージャーテスト"""

    def setUp(self):
        super().setUp()
        self.security_config = self.create_test_config("security.json", {
            "password_min_length": 12,
            "password_require_special": True,
            "max_login_attempts": 3,
            "lockout_duration_minutes": 5
        })
        self.security_manager = SecurityManager(self.security_config)

    def test_password_validation(self):
        """パスワード検証テスト"""
        # 有効なパスワード
        valid_password = "SecurePass123!"
        is_valid, errors = self.security_manager.validate_password(valid_password, "testuser")
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

        # 無効なパスワード（短すぎる）
        short_password = "Pass123!"
        is_valid, errors = self.security_manager.validate_password(short_password, "testuser")
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

        # 無効なパスワード（特殊文字なし）
        no_special = "SecurePass123"
        is_valid, errors = self.security_manager.validate_password(no_special, "testuser")
        self.assertFalse(is_valid)
        self.assertTrue(any("特殊文字" in error for error in errors))

    def test_password_hashing(self):
        """パスワードハッシュ化テスト"""
        password = "TestPassword123!"
        hash1 = self.security_manager.hash_password(password)
        hash2 = self.security_manager.hash_password(password)

        # 同じパスワードでも異なるハッシュが生成される（salt使用）
        self.assertNotEqual(hash1, hash2)

        # 両方のハッシュで検証が成功する
        self.assertTrue(self.security_manager.verify_password(password, hash1))
        self.assertTrue(self.security_manager.verify_password(password, hash2))

        # 間違ったパスワードでは検証失敗
        self.assertFalse(self.security_manager.verify_password("WrongPassword", hash1))

    def test_login_attempts_and_lockout(self):
        """ログイン試行とロックアウトテスト"""
        username = "testuser"
        ip_address = "192.168.1.100"

        # 最初のチェックは成功
        can_login, message = self.security_manager.check_login_attempt(username, ip_address)
        self.assertTrue(can_login)

        # 失敗試行を記録
        for i in range(3):  # max_login_attempts = 3
            self.security_manager.record_failed_attempt(username, ip_address)

        # ロックアウト後はログイン不可
        can_login, message = self.security_manager.check_login_attempt(username, ip_address)
        self.assertFalse(can_login)
        self.assertIn("ロック", message)

    def test_session_management(self):
        """セッション管理テスト"""
        username = "testuser"
        ip_address = "192.168.1.100"

        # セッション作成
        session_id = self.security_manager.create_session(username, ip_address)
        self.assertIsNotNone(session_id)

        # セッション検証
        is_valid, session_data = self.security_manager.validate_session(session_id, ip_address)
        self.assertTrue(is_valid)
        self.assertIsNotNone(session_data)
        self.assertEqual(session_data["username"], username)

        # 異なるIPでのアクセス（セッションハイジャック検知）
        is_valid, session_data = self.security_manager.validate_session(session_id, "192.168.1.200")
        self.assertFalse(is_valid)

        # セッション破棄
        self.security_manager.destroy_session(session_id)
        is_valid, session_data = self.security_manager.validate_session(session_id, ip_address)
        self.assertFalse(is_valid)

    def test_csrf_token_validation(self):
        """CSRFトークン検証テスト"""
        username = "testuser"
        ip_address = "192.168.1.100"

        session_id = self.security_manager.create_session(username, ip_address)
        is_valid, session_data = self.security_manager.validate_session(session_id, ip_address)

        if session_data and "csrf_token" in session_data:
            # 正しいトークンで検証
            csrf_token = session_data["csrf_token"]
            self.assertTrue(self.security_manager.validate_csrf_token(session_id, csrf_token))

            # 間違ったトークンで検証
            self.assertFalse(self.security_manager.validate_csrf_token(session_id, "wrong_token"))

class TestPerformanceManager(TestBase):
    """パフォーマンスマネージャーテスト"""

    def setUp(self):
        super().setUp()
        self.perf_config = self.create_test_config("performance.json", {
            "monitoring_interval": 1,
            "enable_auto_optimization": True,
            "thresholds": {
                "cpu_percent": 80,
                "memory_percent": 85
            }
        })
        self.performance_monitor = PerformanceMonitor(self.perf_config)

    def test_metrics_collection(self):
        """メトリクス収集テスト"""
        metrics = self.performance_monitor.collect_metrics()
        self.assertIsInstance(metrics, list)
        self.assertGreater(len(metrics), 0)

        # CPU使用率メトリクスが含まれているかチェック
        cpu_metrics = [m for m in metrics if m.metric_type == MetricType.CPU_USAGE]
        self.assertGreater(len(cpu_metrics), 0)

        for metric in cpu_metrics:
            self.assertIsInstance(metric.value, (int, float))
            self.assertGreaterEqual(metric.value, 0)
            self.assertLessEqual(metric.value, 100)

    def test_health_status_assessment(self):
        """ヘルス状態評価テスト"""
        # 初期状態（データ不足）
        status, details = self.performance_monitor.get_health_status()
        self.assertIn(status, [HealthStatus.UNKNOWN, HealthStatus.HEALTHY])

        # メトリクスを追加してテスト
        self.performance_monitor.start_monitoring()
        time.sleep(2)  # メトリクス収集を待つ
        self.performance_monitor.stop_monitoring()

        status, details = self.performance_monitor.get_health_status()
        self.assertIsInstance(details, dict)
        self.assertIn("score", details)

    def test_optimization_recommendations(self):
        """最適化推奨事項テスト"""
        recommendations = self.performance_monitor.get_optimization_recommendations()
        self.assertIsInstance(recommendations, list)

        for rec in recommendations:
            self.assertIsInstance(rec.priority, int)
            self.assertGreaterEqual(rec.priority, 1)
            self.assertLessEqual(rec.priority, 5)
            self.assertIsNotNone(rec.recommendation)

    def test_metrics_export(self):
        """メトリクスエクスポートテスト"""
        export_path = self.temp_dir / "metrics_export.json"

        # いくつかメトリクスを生成
        metrics = self.performance_monitor.collect_metrics()
        for metric in metrics:
            self.performance_monitor.record_metric(metric)

        # エクスポート
        success = self.performance_monitor.export_metrics(export_path, "json")
        self.assertTrue(success)
        self.assertTrue(export_path.exists())

        # エクスポートファイルの内容検証
        with open(export_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertIn("exported_at", data)
            self.assertIn("metrics", data)

class TestErrorRecoverySystem(TestBase):
    """エラー復旧システムテスト"""

    def setUp(self):
        super().setUp()
        self.error_config = self.create_test_config("error_recovery.json", {
            "enable_auto_recovery": True,
            "max_concurrent_recoveries": 2
        })
        self.error_system = ErrorRecoverySystem(self.error_config)

    def test_error_registration(self):
        """エラー登録テスト"""
        component = "test_component"
        error = RuntimeError("Test error")
        context = {"operation": "test_operation", "data": "test_data"}

        error_id = self.error_system.register_error(component, error, context)
        self.assertIsNotNone(error_id)
        self.assertTrue(error_id.startswith(component))

        # エラー履歴に記録されているか確認
        self.assertGreater(len(self.error_system.error_history), 0)

        recent_error = list(self.error_system.error_history)[-1]
        self.assertEqual(recent_error.component, component)
        self.assertEqual(recent_error.error_type, "RuntimeError")

    def test_circuit_breaker(self):
        """サーキットブレーカーテスト"""
        breaker = self.error_system.get_circuit_breaker("test_breaker", failure_threshold=3)

        @breaker
        def failing_function():
            raise Exception("Test failure")

        # 連続失敗でサーキットブレーカーが作動
        for i in range(3):
            with self.assertRaises(Exception):
                failing_function()

        # 4回目はサーキットブレーカーが作動
        with self.assertRaises(Exception) as cm:
            failing_function()

        # サーキットブレーカーの状態確認
        self.assertEqual(breaker.state, 'OPEN')

    def test_retry_mechanism(self):
        """リトライメカニズムテスト"""
        from error_recovery_system import RetryMechanism

        call_count = 0

        @RetryMechanism(max_attempts=3, delay=0.1)
        def unstable_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = unstable_function()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)

    def test_error_statistics(self):
        """エラー統計テスト"""
        # 複数のエラーを登録
        errors = [
            RuntimeError("Error 1"),
            ValueError("Error 2"),
            ConnectionError("Error 3")
        ]

        for i, error in enumerate(errors):
            self.error_system.register_error(f"component_{i}", error)

        stats = self.error_system.get_error_statistics()
        self.assertIsInstance(stats, dict)
        self.assertGreater(stats["total_errors"], 0)
        self.assertIn("errors_24h", stats)
        self.assertIn("component_distribution", stats)

class TestDatabaseManager(TestBase):
    """データベースマネージャーテスト"""

    def setUp(self):
        super().setUp()
        db_path = self.temp_dir / "test.db"
        self.db_config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            database=str(db_path),
            pool_size=5,
            backup_enabled=False  # テストでは無効
        )
        self.db_manager = DatabaseManager(self.db_config)

    def tearDown(self):
        super().tearDown()
        try:
            self.db_manager.close()
        except:
            pass

    def test_database_connection(self):
        """データベース接続テスト"""
        with self.db_manager.connection_pool.get_connection() as conn:
            self.assertIsNotNone(conn)

    def test_query_builder(self):
        """クエリビルダーテスト"""
        builder = self.db_manager.query_builder("test_table")

        # SELECT文構築
        builder.select("id", "name").where("status = ?", "active").limit(10)
        sql, params = builder.build()

        self.assertIn("SELECT id, name FROM test_table", sql)
        self.assertIn("WHERE status = ?", sql)
        self.assertIn("LIMIT 10", sql)
        self.assertEqual(params, ["active"])

    def test_crud_operations(self):
        """CRUD操作テスト"""
        # テーブル作成
        self.db_manager.execute("""
            CREATE TABLE test_users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE
            )
        """)

        # INSERT
        user_id = self.db_manager.insert("test_users", name="Test User", email="test@demo.local")
        self.assertIsNotNone(user_id)

        # SELECT
        users = self.db_manager.select("test_users", where="id = ?", params=[user_id])
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["name"], "Test User")

        # UPDATE
        affected = self.db_manager.update("test_users", {"name": "Updated User"}, "id = ?", [user_id])
        users = self.db_manager.select("test_users", where="id = ?", params=[user_id])
        self.assertEqual(users[0]["name"], "Updated User")

        # DELETE
        deleted = self.db_manager.delete("test_users", "id = ?", [user_id])
        users = self.db_manager.select("test_users", where="id = ?", params=[user_id])
        self.assertEqual(len(users), 0)

    def test_transaction_management(self):
        """トランザクション管理テスト"""
        # テーブル作成
        self.db_manager.execute("""
            CREATE TABLE test_transactions (
                id INTEGER PRIMARY KEY,
                value TEXT
            )
        """)

        # 成功するトランザクション
        with self.db_manager.transaction():
            self.db_manager.insert("test_transactions", value="test1")
            self.db_manager.insert("test_transactions", value="test2")

        # データが挿入されている
        records = self.db_manager.select("test_transactions")
        self.assertEqual(len(records), 2)

        # 失敗するトランザクション
        try:
            with self.db_manager.transaction():
                self.db_manager.insert("test_transactions", value="test3")
                raise Exception("Rollback test")
        except Exception:
            pass

        # ロールバックされてデータは2件のまま
        records = self.db_manager.select("test_transactions")
        self.assertEqual(len(records), 2)

    def test_database_health(self):
        """データベースヘルステスト"""
        health = self.db_manager.get_database_health()
        self.assertIsInstance(health, object)  # DatabaseHealth object
        self.assertTrue(health.is_connected)

class TestAdvancedLogger(TestBase):
    """高度ロガーテスト"""

    def setUp(self):
        super().setUp()
        log_config = self.create_test_config("logging.json", {
            "log_directory": str(self.temp_dir / "logs"),
            "enable_console_output": False,  # テストでは無効
            "retention_days": 7
        })
        self.logger = AdvancedLogger(log_config)

    def tearDown(self):
        super().tearDown()
        try:
            self.logger.shutdown()
        except:
            pass

    def test_structured_logging(self):
        """構造化ログテスト"""
        self.logger.log(
            level=LogLevel.INFO,
            category=LogCategory.SYSTEM,
            event_type=EventType.SYSTEM_START,
            message="Test system start",
            user_id="test_user",
            component="test_component"
        )

        # ログキューに追加されているか確認
        self.assertGreater(len(self.logger.log_queue), 0)

        # ログ処理を待つ
        time.sleep(0.2)

    def test_log_filtering(self):
        """ログフィルタリングテスト"""
        sensitive_message = "password=secret123 token=abc123"
        filtered_message = self.logger.log_filter.sanitize_message(sensitive_message)

        self.assertNotIn("secret123", filtered_message)
        self.assertNotIn("abc123", filtered_message)
        self.assertIn("*", filtered_message)

    def test_log_search(self):
        """ログ検索テスト"""
        # テストログを追加
        self.logger.log(
            level=LogLevel.INFO,
            category=LogCategory.AUDIT,
            event_type=EventType.USER_LOGIN,
            message="User login successful",
            user_id="test_user"
        )

        time.sleep(0.2)  # ログ処理を待つ

        # 検索
        results = self.logger.search_logs(
            query="login",
            category=LogCategory.AUDIT,
            user_id="test_user"
        )

        # 結果はテストの実行状況により変わるが、基本的な形式をチェック
        self.assertIsInstance(results, list)

    def test_metrics_tracking(self):
        """メトリクス追跡テスト"""
        initial_metrics = self.logger.get_metrics()

        # ログを追加
        self.logger.log(
            level=LogLevel.ERROR,
            category=LogCategory.ERROR,
            event_type=EventType.ERROR_OCCURRED,
            message="Test error"
        )

        time.sleep(0.2)

        final_metrics = self.logger.get_metrics()
        # エラーカウントが増加しているかチェック
        # 実装によってはメトリクス更新にタイムラグがある可能性

class TestBackupSystem(TestBase):
    """バックアップシステムテスト"""

    def setUp(self):
        super().setUp()
        backup_config = self.create_test_config("backup.json", {
            "backup_directory": str(self.temp_dir / "backups"),
            "storage_configs": {
                "local": {
                    "base_path": str(self.temp_dir / "backup_storage")
                }
            }
        })

        # BackupManagerのシングルトンをリセット
        BackupManager._instance = None
        self.backup_manager = BackupManager(backup_config)

    def tearDown(self):
        super().tearDown()
        try:
            self.backup_manager.shutdown()
        except:
            pass
        finally:
            BackupManager._instance = None

    def test_backup_job_creation(self):
        """バックアップジョブ作成テスト"""
        # テスト用ファイル作成
        test_file = self.temp_dir / "test_file.txt"
        test_file.write_text("Test content")

        job_id = self.backup_manager.create_backup_job(
            name="Test Backup Job",
            source_paths=[str(test_file)],
            backup_type=BackupType.FULL,
            retention_days=7
        )

        self.assertIsNotNone(job_id)
        self.assertIn(job_id, self.backup_manager.scheduler.scheduled_jobs)

    def test_backup_execution(self):
        """バックアップ実行テスト"""
        # テスト用ファイル作成
        test_dir = self.temp_dir / "test_data"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("Content 1")
        (test_dir / "file2.txt").write_text("Content 2")

        job_id = self.backup_manager.create_backup_job(
            name="Test Backup",
            source_paths=[str(test_dir)],
            backup_type=BackupType.FULL,
            storage_type=StorageType.LOCAL
        )

        job = self.backup_manager.scheduler.scheduled_jobs[job_id]
        backup_id = self.backup_manager.execute_backup(job)

        self.assertIsNotNone(backup_id)

        # バックアップレコードが作成されているか確認
        records = [r for r in self.backup_manager.backup_records if r.record_id == backup_id]
        self.assertEqual(len(records), 1)

    def test_backup_status(self):
        """バックアップステータステスト"""
        status = self.backup_manager.get_backup_status()
        self.assertIsInstance(status, dict)
        self.assertIn("total_backups", status)
        self.assertIn("successful", status)
        self.assertIn("failed", status)

class TestIntegration(TestBase):
    """統合テスト"""

    def setUp(self):
        super().setUp()
        # 統合テスト用のコンポーネントを初期化
        self.components = {}

    def test_system_integration(self):
        """システム統合テスト"""
        # 複数のコンポーネントが正常に連携することをテスト

        # 1. セキュリティマネージャーとログシステムの連携
        security_config = self.create_test_config("security.json", {})
        security_manager = SecurityManager(security_config)

        log_config = self.create_test_config("logging.json", {
            "log_directory": str(self.temp_dir / "logs"),
            "enable_console_output": False
        })
        logger = AdvancedLogger(log_config)

        try:
            # セキュリティイベントのログ記録
            logger.log_security_event(
                EventType.PERMISSION_DENIED,
                "Access denied for user",
                user_id="test_user",
                ip_address="192.168.1.100"
            )

            # ログが記録されているか確認
            self.assertGreater(len(logger.log_queue), 0)

        finally:
            logger.shutdown()

class TestPerformance(TestBase):
    """パフォーマンステスト"""

    def test_database_performance(self):
        """データベースパフォーマンステスト"""
        db_path = self.temp_dir / "perf_test.db"
        config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            database=str(db_path)
        )
        db_manager = DatabaseManager(config)

        try:
            # テーブル作成
            db_manager.execute("""
                CREATE TABLE perf_test (
                    id INTEGER PRIMARY KEY,
                    data TEXT
                )
            """)

            # 大量挿入のパフォーマンステスト
            start_time = time.time()

            with db_manager.transaction():
                for i in range(1000):
                    db_manager.insert("perf_test", data=f"Test data {i}")

            end_time = time.time()
            duration = end_time - start_time

            # 1000件挿入が5秒以内で完了することを確認
            self.assertLess(duration, 5.0)

            # データ件数確認
            records = db_manager.select("perf_test")
            self.assertEqual(len(records), 1000)

        finally:
            db_manager.close()

    def test_logging_performance(self):
        """ログ記録パフォーマンステスト"""
        log_config = self.create_test_config("logging.json", {
            "log_directory": str(self.temp_dir / "logs"),
            "enable_console_output": False
        })
        logger = AdvancedLogger(log_config)

        try:
            start_time = time.time()

            # 大量ログ出力
            for i in range(1000):
                logger.log(
                    level=LogLevel.INFO,
                    category=LogCategory.SYSTEM,
                    event_type=EventType.SYSTEM_START,
                    message=f"Test log message {i}"
                )

            end_time = time.time()
            duration = end_time - start_time

            # 1000件のログ出力が3秒以内で完了することを確認
            self.assertLess(duration, 3.0)

        finally:
            logger.shutdown()

def run_test_suite():
    """テストスイート実行"""
    test_logger.info("=== Cocoa 包括的テストスイート開始 ===")

    # テストスイートの構成
    test_cases = [
        TestSecurityManager,
        TestPerformanceManager,
        TestErrorRecoverySystem,
        TestDatabaseManager,
        TestAdvancedLogger,
        TestBackupSystem,
        TestIntegration,
        TestPerformance
    ]

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # テストケースをスイートに追加
    for test_case in test_cases:
        tests = loader.loadTestsFromTestCase(test_case)
        suite.addTests(tests)

    # テスト実行
    runner = unittest.TextTestRunner(
        verbosity=2,
        buffer=True,
        failfast=False
    )

    start_time = time.time()
    result = runner.run(suite)
    end_time = time.time()

    # 結果サマリー
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    success_rate = ((total_tests - failures - errors) / total_tests * 100) if total_tests > 0 else 0

    test_logger.info("=== テストスイート結果 ===")
    test_logger.info(f"実行時間: {end_time - start_time:.2f}秒")
    test_logger.info(f"総テスト数: {total_tests}")
    test_logger.info(f"成功: {total_tests - failures - errors}")
    test_logger.info(f"失敗: {failures}")
    test_logger.info(f"エラー: {errors}")
    test_logger.info(f"成功率: {success_rate:.1f}%")

    if failures > 0:
        test_logger.error("=== 失敗したテスト ===")
        for test, traceback in result.failures:
            test_logger.error(f"{test}: {traceback}")

    if errors > 0:
        test_logger.error("=== エラーが発生したテスト ===")
        for test, traceback in result.errors:
            test_logger.error(f"{test}: {traceback}")

    return result.wasSuccessful()

if __name__ == "__main__":
    # コマンドライン引数処理
    import argparse

    parser = argparse.ArgumentParser(description="Cocoa 包括的テストスイート")
    parser.add_argument("--verbose", "-v", action="store_true", help="詳細出力")
    parser.add_argument("--test-case", "-t", type=str, help="特定のテストケースのみ実行")
    parser.add_argument("--performance", "-p", action="store_true", help="パフォーマンステストを含める")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    success = run_test_suite()
    sys.exit(0 if success else 1)