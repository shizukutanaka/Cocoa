"""
pytest グローバル設定ファイル
すべてのテストで共有される fixture と設定

ファイル配置: tests/conftest.py
自動的に pytest により検出される
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

# プロジェクトルートを sys.path に追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# テスト環境の設定
os.environ['ENVIRONMENT'] = 'test'
os.environ['LOG_LEVEL'] = 'DEBUG'


# ==================== Session Fixtures ====================
# テストセッション全体で実行（最初と最後）

@pytest.fixture(scope="session")
def test_config():
    """テスト用の設定オブジェクト"""
    from main.config import Config

    config = Config(env="test")
    return config


# ==================== Function Fixtures ====================
# 各テスト関数ごとに実行

@pytest.fixture
def mock_config(test_config):
    """モック化した設定オブジェクト"""
    return MagicMock(spec=test_config.__class__)


@pytest.fixture
def mock_logger():
    """モック化したロガー"""
    logger = MagicMock()
    logger.debug = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.exception = MagicMock()
    return logger


@pytest.fixture
def temp_dir(tmp_path):
    """一時ディレクトリ"""
    return tmp_path


@pytest.fixture
def cleanup():
    """テスト後のクリーンアップ"""
    yield
    # クリーンアップ処理
    pass


# ==================== Database Fixtures ====================
# データベース関連テスト用

@pytest.fixture
def mock_database():
    """モック化したデータベース接続"""
    db = MagicMock()
    db.connect = MagicMock(return_value=True)
    db.close = MagicMock()
    db.execute = MagicMock()
    return db


# ==================== API Fixtures ====================
# FastAPI テスト用

@pytest.fixture
def mock_http_client():
    """モック化したHTTP クライアント"""
    from unittest.mock import AsyncMock

    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    return client


# ==================== Security Fixtures ====================
# セキュリティ関連テスト用

@pytest.fixture
def mock_security_manager():
    """モック化したセキュリティマネージャー"""
    security = MagicMock()
    security.encrypt = MagicMock(return_value=b"encrypted_data")
    security.decrypt = MagicMock(return_value="decrypted_data")
    security.validate_password = MagicMock(return_value=True)
    security.generate_token = MagicMock(return_value="token_123")
    return security


# ==================== Async Fixtures ====================
# 非同期テスト用

@pytest.fixture
def event_loop():
    """イベントループの管理"""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_client():
    """非同期HTTP クライアント"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    return client


# ==================== Parametrize Helpers ====================
# パラメーター化テスト用

@pytest.fixture(params=[
    {"name": "test_avatar_1", "status": "active"},
    {"name": "test_avatar_2", "status": "inactive"},
])
def avatar_params(request):
    """複数のアバターパラメーター"""
    return request.param


# ==================== Markers ====================
# テストカテゴリ分け

def pytest_configure(config):
    """pytest カスタムマーカーを登録"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security-related"
    )
    config.addinivalue_line(
        "markers", "asyncio: marks tests as asynchronous"
    )


# ==================== Hooks ====================
# pytest の実行フローをカスタマイズ

@pytest.fixture(autouse=True)
def reset_globals():
    """グローバル状態をリセット"""
    yield
    # テスト後のリセット処理
    from main.dependency_injection import init_container
    from main.logging_config import set_correlation_id

    init_container()
    set_correlation_id(None)


def pytest_collection_modifyitems(config, items):
    """テスト実行前に実行"""
    for item in items:
        # 非同期テストに asyncio marker を自動追加
        if "async" in item.nodeid:
            item.add_marker(pytest.mark.asyncio)


# ==================== Custom Assertions ====================
# カスタムアサーション

class CustomAssertions:
    """カスタムアサーション集"""

    @staticmethod
    def assert_valid_uuid(uuid_str: str) -> None:
        """有効なUUID かどうかを確認"""
        import uuid

        try:
            uuid.UUID(uuid_str)
        except ValueError:
            raise AssertionError(f"{uuid_str} is not a valid UUID") from None

    @staticmethod
    def assert_is_json(data: str) -> None:
        """有効なJSON かどうかを確認"""
        import json

        try:
            json.loads(data)
        except json.JSONDecodeError:
            raise AssertionError(f"{data} is not valid JSON") from None

    @staticmethod
    def assert_log_called(mock_logger, level: str, count: int = 1) -> None:
        """ロガーメソッドが呼ばれたかを確認"""
        log_method = getattr(mock_logger, level, None)
        if log_method is None:
            raise AssertionError(f"Logger has no method '{level}'")

        if log_method.call_count != count:
            raise AssertionError(
                f"Logger.{level}() was called {log_method.call_count} times, "
                f"expected {count}"
            )


@pytest.fixture
def assertions():
    """カスタムアサーションを提供"""
    return CustomAssertions()
