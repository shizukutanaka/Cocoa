"""
新しい機能のテストケース
設定ファイル暗号化とキャッシュマネージャーのテスト
"""

import json
import tempfile
import time
import unittest
from pathlib import Path

# 新しい機能のインポート
try:
    from main.cache_manager import CacheManager, FileCache, MemoryCache, cached
    from main.config_encryptor import (
        ConfigEncryptor,
        decrypt_config_file,
        encrypt_config_file,
    )
    CONFIG_ENCRYPTOR_AVAILABLE = True
except ImportError as e:
    print(f"テスト対象モジュールがインポートできません: {e}")
    CONFIG_ENCRYPTOR_AVAILABLE = False

try:
    from main.logging_manager import LoggingManager
    LOGGING_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"ログマネージャーがインポートできません: {e}")
    LOGGING_MANAGER_AVAILABLE = False


class TestConfigEncryptor(unittest.TestCase):
    """設定ファイル暗号化機能のテスト"""

    def setUp(self):
        """テスト前の準備"""
        if not CONFIG_ENCRYPTOR_AVAILABLE:
            self.skipTest("ConfigEncryptorが利用できません")

        self.test_config = {
            'app_name': 'Test App',
            'database': {
                'host': 'localhost',
                'password': 'secret_password',
                'api_key': 'test_api_key_12345'
            },
            'smtp': {
                'server': 'smtp.example.com',
                'port': 587,
                'username': 'test@example.com',
                'password_env': 'SMTP_PASSWORD'
            },
            'normal_setting': 'normal_value'
        }

    def test_config_encryption_decryption(self):
        """設定ファイルの暗号化・復号化テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 元の設定ファイルを作成
            config_file = Path(temp_dir) / 'test_config.json'
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.test_config, f, indent=2)

            # 暗号化キーを設定
            test_key = 'test_encryption_key_32_chars!!'

            # 暗号化
            encrypted_file = Path(temp_dir) / 'encrypted_config'
            encryptor = ConfigEncryptor(test_key)
            success = encryptor.encrypt_config_file(str(config_file), str(encrypted_file))
            self.assertTrue(success)
            self.assertTrue(encrypted_file.exists())

            # 復号化
            decrypted_file = Path(temp_dir) / 'decrypted_config.json'
            success = encryptor.decrypt_config_file(str(encrypted_file), str(decrypted_file))
            self.assertTrue(success)
            self.assertTrue(decrypted_file.exists())

            # 復号化された内容を確認
            with open(decrypted_file, encoding='utf-8') as f:
                decrypted_config = json.load(f)

            # 機密フィールドがマスクされていることを確認
            self.assertEqual(decrypted_config['app_name'], 'Test App')
            self.assertEqual(decrypted_config['database']['host'], 'localhost')
            self.assertEqual(decrypted_config['database']['password'], '***MASKED***')
            self.assertEqual(decrypted_config['database']['api_key'], '***MASKED***')
            self.assertEqual(decrypted_config['smtp']['server'], 'smtp.example.com')
            self.assertEqual(decrypted_config['normal_setting'], 'normal_value')

    def test_sensitive_data_masking(self):
        """機密データのマスク機能テスト"""
        if not CONFIG_ENCRYPTOR_AVAILABLE:
            self.skipTest("ConfigEncryptorが利用できません")

        encryptor = ConfigEncryptor()

        # マスク処理のテスト
        masked = encryptor._mask_sensitive_data(self.test_config)

        # マスクされていることを確認
        self.assertEqual(masked['database']['password'], '***MASKED***')
        self.assertEqual(masked['database']['api_key'], '***MASKED***')
        self.assertEqual(masked['app_name'], 'Test App')  # マスク対象外
        self.assertEqual(masked['normal_setting'], 'normal_value')  # マスク対象外

    def test_convenience_functions(self):
        """便利関数のテスト"""
        if not CONFIG_ENCRYPTOR_AVAILABLE:
            self.skipTest("ConfigEncryptorが利用できません")

        with tempfile.TemporaryDirectory() as temp_dir:
            # 元の設定ファイルを作成
            config_file = Path(temp_dir) / 'test_config.json'
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.test_config, f, indent=2)

            # 便利関数での暗号化・復号化
            test_key = 'test_encryption_key_for_convenience'

            # 暗号化
            success = encrypt_config_file(str(config_file), test_key)
            self.assertTrue(success)

            # 暗号化ファイルの存在確認
            encrypted_file = config_file.with_suffix('.encrypted')
            self.assertTrue(encrypted_file.exists())

            # 復号化
            success = decrypt_config_file(str(encrypted_file), test_key)
            self.assertTrue(success)


class TestCacheManager(unittest.TestCase):
    """キャッシュマネージャーのテスト"""

    def setUp(self):
        """テスト前の準備"""
        self.cache_manager = CacheManager({
            'memory_cache_size': 10,
            'memory_cache_ttl': 1,  # 1秒の短いTTLでテスト
            'file_cache_dir': None,  # メモリキャッシュのみ使用
            'cache_strategy': 'memory_first'
        })

    def test_memory_cache_basic_operations(self):
        """メモリキャッシュの基本操作テスト"""
        # キャッシュへの保存
        self.cache_manager.set('test_key', 'test_value')
        self.assertEqual(self.cache_manager.get('test_key'), 'test_value')

        # 存在しないキーのテスト
        self.assertIsNone(self.cache_manager.get('nonexistent_key'))

        # キャッシュの無効化
        self.cache_manager.invalidate('test_key')
        self.assertIsNone(self.cache_manager.get('test_key'))

    def test_cache_ttl(self):
        """キャッシュTTLのテスト"""
        # 短いTTLでテスト
        cache = MemoryCache(max_size=10, ttl_seconds=1)

        # データの保存
        cache.set('ttl_test', 'test_value')
        self.assertEqual(cache.get('ttl_test'), 'test_value')

        # TTL経過待ち
        time.sleep(1.1)

        # TTL経過後、データが取得できないことを確認
        self.assertIsNone(cache.get('ttl_test'))

    def test_cache_size_limit(self):
        """キャッシュサイズ制限のテスト"""
        # 小さなサイズ制限でテスト
        cache = MemoryCache(max_size=2, ttl_seconds=300)

        # データを追加
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')

        # サイズ制限を超えるデータを追加
        cache.set('key3', 'value3')

        # 最初のデータが削除されていることを確認（LRU）
        self.assertIsNone(cache.get('key1'))
        self.assertEqual(cache.get('key2'), 'value2')
        self.assertEqual(cache.get('key3'), 'value3')

    def test_file_cache_operations(self):
        """ファイルキャッシュのテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_cache = FileCache(cache_dir=temp_dir, ttl_seconds=300)

            # データの保存と取得
            test_key = 'file_cache_test'
            test_value = {'data': 'test_data', 'number': 42}

            file_cache.set(test_key, test_value)
            retrieved_value = file_cache.get(test_key)

            self.assertEqual(retrieved_value, test_value)

            # ファイルの存在確認
            cache_file = file_cache._get_cache_path(test_key)
            self.assertTrue(cache_file.exists())

            # キャッシュのクリア
            file_cache.clear()
            self.assertIsNone(file_cache.get(test_key))

    def test_cache_decorator(self):
        """キャッシュデコレーターのテスト"""
        @cached(ttl_seconds=5)
        def expensive_function(x, y):
            # 関数呼び出しを記録するためのグローバル変数
            expensive_function.call_count = getattr(expensive_function, 'call_count', 0) + 1
            return x + y

        # リセット
        expensive_function.call_count = 0

        # 初回呼び出し
        result1 = expensive_function(1, 2)
        self.assertEqual(result1, 3)
        self.assertEqual(expensive_function.call_count, 1)

        # 同じ引数での呼び出し（キャッシュから取得されるはず）
        result2 = expensive_function(1, 2)
        self.assertEqual(result2, 3)
        self.assertEqual(expensive_function.call_count, 1)  # 呼び出し回数が変わらないことを確認

        # 異なる引数での呼び出し
        result3 = expensive_function(2, 3)
        self.assertEqual(result3, 5)
        self.assertEqual(expensive_function.call_count, 2)  # 新しい呼び出しが発生することを確認

    def test_cache_statistics(self):
        """キャッシュ統計機能のテスト"""
        # いくつかの操作を実行
        self.cache_manager.set('stat_key1', 'value1')
        self.cache_manager.set('stat_key2', 'value2')
        self.cache_manager.get('stat_key1')  # アクセス

        # 統計情報を取得
        stats = self.cache_manager.get_stats()

        # 統計情報の構造を確認
        self.assertIn('memory_cache', stats)
        self.assertIn('file_cache', stats)
        self.assertIn('strategy', stats)

        # メモリキャッシュの統計を確認
        memory_stats = stats['memory_cache']
        self.assertIn('size', memory_stats)
        self.assertIn('max_size', memory_stats)


class TestLoggingManager(unittest.TestCase):
    """ログマネージャーのテスト"""

    def setUp(self):
        """テスト前の準備"""
        if not LOGGING_MANAGER_AVAILABLE:
            self.skipTest("LoggingManagerが利用できません")

        self.test_config = {
            'log_dir': None,  # メモリ上でのテスト
            'log_level': 'INFO',
            'enable_console': False,  # テストではコンソール出力を抑止
            'enable_json_format': True,
            'enable_error_tracking': False,  # テストではエラートラッキングを無効化
            'error_threshold': 5,
            'error_alerts_enabled': False
        }

    def test_logging_manager_initialization(self):
        """ログマネージャーの初期化テスト"""
        logging_manager = LoggingManager(self.test_config)

        # 初期化後の状態を確認
        self.assertIsNotNone(logging_manager.log_dir)
        self.assertEqual(logging_manager.log_level, 'INFO')
        self.assertFalse(logging_manager.enable_console)

    def test_log_level_setting(self):
        """ログレベルの設定テスト"""
        logging_manager = LoggingManager(self.test_config)

        # ログレベルの変更
        success = logging_manager.set_log_level('DEBUG')
        self.assertTrue(success)
        self.assertEqual(logging_manager.log_level, 'DEBUG')

        # 無効なログレベルのテスト
        success = logging_manager.set_log_level('INVALID')
        self.assertFalse(success)

    def test_log_message_recording(self):
        """ログメッセージ記録のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_config = self.test_config.copy()
            test_config['log_dir'] = temp_dir

            logging_manager = LoggingManager(test_config)

            # ログメッセージの記録
            logging_manager.log_message('INFO', 'テストメッセージ', {'test': True})

            # ログファイルの確認（簡易的にファイルが存在することを確認）
            log_files = list(Path(temp_dir).glob('*.log'))
            self.assertTrue(len(log_files) > 0)

    def test_avatar_log_recording(self):
        """アバターログ記録のテスト"""
        logging_manager = LoggingManager(self.test_config)

        # アバターログの記録
        logging_manager.log_avatar_action('avatar_123', 'load', 0.5, True)

        # エラーハンドリングのテスト（例外が発生しないことを確認）
        try:
            logging_manager.log_avatar_action('avatar_456', 'save', 1.2, False)
        except Exception as e:
            self.fail(f"アバターログ記録で予期しない例外が発生しました: {e}")

    def test_log_search_functionality(self):
        """ログ検索機能のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_config = self.test_config.copy()
            test_config['log_dir'] = temp_dir

            logging_manager = LoggingManager(test_config)

            # 複数のログメッセージを記録
            logging_manager.log_message('INFO', 'テストメッセージ1', {'id': 1})
            logging_manager.log_message('WARNING', 'テストメッセージ2', {'id': 2})
            logging_manager.log_message('ERROR', 'テストメッセージ3', {'id': 3})

            # ログ検索のテスト
            results = logging_manager.search_logs('テストメッセージ', limit=10)

            # 検索結果の確認
            self.assertTrue(len(results) >= 3)  # 少なくとも3件の結果があるはず

            # 各結果に必要なフィールドがあることを確認
            for result in results:
                self.assertIn('message', result)

    def test_log_statistics(self):
        """ログ統計機能のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_config = self.test_config.copy()
            test_config['log_dir'] = temp_dir

            logging_manager = LoggingManager(test_config)

            # いくつかのログを記録
            for i in range(5):
                logging_manager.log_message('INFO', f'統計テストメッセージ{i}', {'index': i})

            # 統計情報を取得
            stats = logging_manager.get_log_stats()

            # 統計情報の構造を確認
            self.assertIn('file_size', stats)
            self.assertIn('line_count', stats)
            self.assertIn('log_level', stats)

            # ファイルサイズが0より大きいことを確認
            self.assertGreater(stats['file_size'], 0)

    def test_log_export_functionality(self):
        """ログエクスポート機能のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_config = self.test_config.copy()
            test_config['log_dir'] = temp_dir

            logging_manager = LoggingManager(test_config)

            # ログを記録
            logging_manager.log_message('INFO', 'エクスポートテストメッセージ')

            # ログのエクスポート
            export_file = Path(temp_dir) / 'exported_logs.json'
            success = logging_manager.export_logs(str(export_file), format='json')

            # エクスポート成功を確認
            self.assertTrue(success)
            self.assertTrue(export_file.exists())

            # エクスポートされたファイルの内容を確認
            with open(export_file, encoding='utf-8') as f:
                exported_data = json.load(f)

            self.assertIsInstance(exported_data, list)
            self.assertGreater(len(exported_data), 0)


class TestIntegrationFeatures(unittest.TestCase):
    """統合機能のテスト"""

    def test_end_to_end_workflow(self):
        """エンドツーエンドのワークフローテスト"""
        if not CONFIG_ENCRYPTOR_AVAILABLE:
            self.skipTest("必要なモジュールが利用できません")

        with tempfile.TemporaryDirectory() as temp_dir:
            # 1. 設定ファイルの作成
            config_file = Path(temp_dir) / 'workflow_config.json'
            test_config = {
                'app_name': 'Workflow Test',
                'secret_key': 'super_secret_key_12345',
                'normal_setting': 'normal_value'
            }

            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(test_config, f, indent=2)

            # 2. 設定ファイルの暗号化
            encryptor = ConfigEncryptor('test_key_for_workflow')
            encrypted_file = Path(temp_dir) / 'encrypted_config'

            success = encryptor.encrypt_config_file(str(config_file), str(encrypted_file))
            self.assertTrue(success)

            # 3. 暗号化ファイルの復号化
            decrypted_file = Path(temp_dir) / 'decrypted_config.json'
            success = encryptor.decrypt_config_file(str(encrypted_file), str(decrypted_file))
            self.assertTrue(success)

            # 4. 復号化された内容の確認
            with open(decrypted_file, encoding='utf-8') as f:
                final_config = json.load(f)

            self.assertEqual(final_config['app_name'], 'Workflow Test')
            self.assertEqual(final_config['secret_key'], '***MASKED***')
            self.assertEqual(final_config['normal_setting'], 'normal_value')

    def test_performance_improvements(self):
        """パフォーマンス向上機能のテスト"""
        # キャッシュ機能のパフォーマンステスト
        cache_manager = CacheManager({
            'memory_cache_size': 100,
            'memory_cache_ttl': 300,
            'cache_strategy': 'memory_first'
        })

        # キャッシュの効果測定
        start_time = time.time()

        # 初回アクセス（キャッシュなし）
        result1 = cache_manager.get('performance_test_key')

        # データの保存
        cache_manager.set('performance_test_key', 'test_value')

        # 2回目アクセス（キャッシュあり）
        result2 = cache_manager.get('performance_test_key')

        end_time = time.time()

        # 結果の確認
        self.assertIsNone(result1)  # 初回はNone
        self.assertEqual(result2, 'test_value')  # 2回目は値が返る
        self.assertLess(end_time - start_time, 1.0)  # 処理時間が1秒未満であることを確認


class TestPerformanceOptimization(unittest.TestCase):
    """パフォーマンス最適化機能のテスト"""

    def setUp(self):
        """テスト前の準備"""
        self.temp_dir = tempfile.mkdtemp()

    def test_async_cache_performance(self):
        """非同期キャッシュのパフォーマンステスト"""
        try:
            from main.cache_manager import AsyncCacheManager
        except ImportError:
            self.skipTest("AsyncCacheManagerが利用できません")

        async def run_performance_test():
            cache_manager = AsyncCacheManager({
                'memory_cache_size': 1000,
                'memory_cache_ttl': 300
            })

            # パフォーマンス測定の開始
            start_time = time.time()

            # 複数のキャッシュ操作を実行
            for i in range(100):
                await cache_manager.set(f'key_{i}', f'value_{i}')
                await cache_manager.get(f'key_{i}')

            end_time = time.time()
            duration = end_time - start_time

            # 100回の操作が1秒以内に完了することを確認
            self.assertLess(duration, 1.0, f"キャッシュ操作が遅すぎます: {duration}秒")

            return duration

        # 非同期テストを実行
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            duration = loop.run_until_complete(run_performance_test())
            print(f"非同期キャッシュパフォーマンステスト完了: {duration:.3f}秒")
        finally:
            loop.close()

    def test_memory_cache_performance(self):
        """メモリキャッシュのパフォーマンステスト"""
        if not CONFIG_ENCRYPTOR_AVAILABLE:
            self.skipTest("キャッシュ機能が利用できません")

        cache_manager = CacheManager({
            'memory_cache_size': 1000,
            'memory_cache_ttl': 300
        })

        # パフォーマンス測定の開始
        start_time = time.time()

        # 複数のキャッシュ操作を実行
        for i in range(1000):
            cache_manager.set(f'perf_key_{i}', f'perf_value_{i}')
            cache_manager.get(f'perf_key_{i}')

        end_time = time.time()
        duration = end_time - start_time

        # 1000回の操作が2秒以内に完了することを確認
        self.assertLess(duration, 2.0, f"メモリキャッシュ操作が遅すぎます: {duration}秒")

        # 統計情報の確認
        stats = cache_manager.get_stats()
        self.assertEqual(stats['memory_cache']['size'], 1000)

    def test_file_cache_performance(self):
        """ファイルキャッシュのパフォーマンステスト"""
        if not CONFIG_ENCRYPTOR_AVAILABLE:
            self.skipTest("キャッシュ機能が利用できません")

        cache_dir = Path(self.temp_dir) / 'test_cache'
        cache_manager = CacheManager({
            'file_cache_dir': str(cache_dir),
            'file_cache_ttl': 3600
        })

        # パフォーマンス測定の開始
        start_time = time.time()

        # ファイルキャッシュ操作を実行
        for i in range(100):
            cache_manager.set(f'file_key_{i}', f'file_value_{i}', use_file_cache=True)
            cache_manager.get(f'file_key_{i}')

        end_time = time.time()
        duration = end_time - start_time

        # ファイルキャッシュはメモリキャッシュより遅いが、許容範囲内であることを確認
        self.assertLess(duration, 5.0, f"ファイルキャッシュ操作が遅すぎます: {duration}秒")

    def test_cache_decorator_performance(self):
        """キャッシュデコレーターのパフォーマンステスト"""
        if not CONFIG_ENCRYPTOR_AVAILABLE:
            self.skipTest("キャッシュ機能が利用できません")

        @cached(ttl_seconds=300)
        def expensive_function(n):
            # 擬似的な高負荷処理
            time.sleep(0.001)  # 1msの処理時間
            return n * n

        # 初回呼び出し（キャッシュなし）
        start_time = time.time()
        result1 = expensive_function(42)
        first_call_duration = time.time() - start_time

        # 2回目呼び出し（キャッシュあり）
        start_time = time.time()
        result2 = expensive_function(42)
        second_call_duration = time.time() - start_time

        # 結果の確認
        self.assertEqual(result1, 1764)
        self.assertEqual(result2, 1764)

        # キャッシュによる高速化を確認（2回目は10倍以上速いはず）
        self.assertLess(second_call_duration, first_call_duration / 10)

    def test_concurrent_cache_access(self):
        """同時アクセス時のキャッシュパフォーマンステスト"""
        if not CONFIG_ENCRYPTOR_AVAILABLE:
            self.skipTest("キャッシュ機能が利用できません")

        cache_manager = CacheManager({
            'memory_cache_size': 10000,
            'memory_cache_ttl': 300
        })

        def worker_thread(thread_id):
            """ワーカースレッドの処理"""
            for i in range(100):
                key = f'thread_{thread_id}_key_{i}'
                value = f'thread_{thread_id}_value_{i}'
                cache_manager.set(key, value)
                result = cache_manager.get(key)
                assert result == value

        # 複数のスレッドで同時アクセス
        import threading
        threads = []
        start_time = time.time()

        for i in range(10):
            thread = threading.Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()

        # 全スレッドの完了を待機
        for thread in threads:
            thread.join()

        end_time = time.time()
        duration = end_time - start_time

        # 同時アクセスのパフォーマンス確認（10スレッド×100操作が5秒以内に完了）
        self.assertLess(duration, 5.0, f"同時アクセス時のパフォーマンスが低下: {duration}秒")


if __name__ == '__main__':
    # テストスイートの実行
    unittest.main(verbosity=2)
