# Cocoa 開発ベストプラクティスガイド

**対象**: 開発チーム全体
**更新日**: 2025-11-03
**言語**: Python 3.8+

---

## 📋 目次

1. [ロギング](#ロギング)
2. [テスト](#テスト)
3. [型チェック](#型チェック)
4. [コード品質](#コード品質)
5. [非同期プログラミング](#非同期プログラミング)
6. [セキュリティ](#セキュリティ)
7. [パフォーマンス](#パフォーマンス)

---

## ロギング

### 基本的な使い方

```python
from main.logging_config import get_logger

logger = get_logger(__name__)

# 通常のログ出力
logger.debug("Debug information")
logger.info("Application started")
logger.warning("Configuration warning")
logger.error("Error occurred")

# 例外ログ（スタックトレース自動追加）
try:
    result = risky_operation()
except Exception:
    logger.exception("Operation failed")  # 推奨: スタックトレース含む
```

### 相関IDの使用（マイクロサービス対応）

```python
from main.logging_config import set_correlation_id, get_logger

# FastAPI ミドルウェアまたはハンドラー内
@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    import uuid
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    set_correlation_id(correlation_id)
    response = await call_next(request)
    return response

# ロガーから自動的に相関IDを含める
logger = get_logger(__name__)
logger.info("Processing request")  # ログに correlation_id が含まれる
```

### 本番環境でのログ設定

```python
from main.logging_config import setup_production_logging

# アプリケーション起動時に呼び出し
if __name__ == "__main__":
    setup_production_logging()  # 環境変数から自動設定
```

**環境変数**:
```bash
ENVIRONMENT=production
LOG_LEVEL=WARNING        # 本番は最小限
LOG_FILE=logs/cocoa.log
```

---

## テスト

### 基本的なテスト構造

```python
# tests/test_avatar_generator.py
import pytest
from unittest.mock import Mock, patch
from main.avatar_generator import AvatarGenerator


class TestAvatarGenerator:
    """AvatarGenerator のテストスイート"""

    @pytest.fixture
    def generator(self, test_config):
        """各テスト前に初期化"""
        return AvatarGenerator(config=test_config)

    def test_generate_avatar(self, generator):
        """アバター生成のテスト"""
        result = generator.generate(user_id="user_123")
        assert result is not None
        assert hasattr(result, 'id')

    @pytest.mark.asyncio
    async def test_generate_avatar_async(self, generator):
        """非同期アバター生成のテスト"""
        result = await generator.generate_async(user_id="user_123")
        assert result is not None
```

### Fixture の活用

```python
@pytest.fixture
def mock_database(mock_database):
    """データベースモック"""
    mock_database.execute.return_value = [{"id": 1, "name": "test"}]
    return mock_database

@pytest.fixture(params=[10, 100, 1000])
def batch_sizes(request):
    """複数のバッチサイズでテスト"""
    return request.param

def test_batch_processing(batch_sizes):
    """異なるバッチサイズでのテスト"""
    result = process_batch(size=batch_sizes)
    assert len(result) == batch_sizes
```

### Mocking ベストプラクティス

```python
from unittest.mock import patch, MagicMock
import pytest

# 1. 外部サービスのモック
@patch('main.avatar_generator.external_api.call')
def test_with_mocked_external_service(mock_api):
    """外部サービスを呼び出す処理のテスト"""
    mock_api.return_value = {"status": "success"}

    result = generate_avatar()
    assert result["status"] == "success"
    mock_api.assert_called_once()

# 2. 非同期関数のモック
@pytest.mark.asyncio
async def test_async_function_with_mock(mock_logger):
    """非同期関数で logger を使用"""
    result = await async_operation()

    mock_logger.info.assert_called()

# 3. データベース操作のモック
def test_database_operation(mock_database):
    """データベース操作のテスト"""
    mock_database.execute.return_value = [{"id": 1}]

    result = get_users()
    assert len(result) == 1
    mock_database.execute.assert_called_with("SELECT * FROM users")
```

### テスト実行

```bash
# 全テストを実行
pytest tests/ -v

# カバレッジレポート付き
pytest tests/ --cov=main --cov-report=html

# 特定のテストのみ実行
pytest tests/test_avatar_generator.py::TestAvatarGenerator::test_generate_avatar

# マーカーで実行
pytest tests/ -m "not slow"  # slow マーカーを除外
pytest tests/ -m "security"  # security マーカーのみ
```

---

## 型チェック

### 基本的な型ヒント

```python
from typing import List, Optional, Dict, Tuple, Union
from dataclasses import dataclass

# 関数の型ヒント
def generate_avatar(user_id: str, options: Optional[Dict[str, str]] = None) -> str:
    """
    アバターを生成

    Args:
        user_id: ユーザーID
        options: オプション設定

    Returns:
        生成されたアバター ID
    """
    return "avatar_123"

# クラスの型ヒント
@dataclass
class Avatar:
    id: str
    user_id: str
    status: str
    tags: List[str]
    metadata: Dict[str, Union[str, int]]

# Union 型
def process_input(data: Union[str, int, List[str]]) -> str:
    """複数の型を受け付ける"""
    pass

# Callable 型
from typing import Callable

def apply_filter(
    items: List[str],
    filter_func: Callable[[str], bool]
) -> List[str]:
    """フィルター関数を受け付ける"""
    return [item for item in items if filter_func(item)]
```

### mypy での検証

```bash
# 全ファイルをチェック
mypy main/

# 特定のファイルをチェック
mypy main/config.py

# 厳密モードで実行
mypy --strict main/

# 段階的に導入
mypy --follow-imports=skip main/
```

### pyproject.toml での設定

```toml
[tool.mypy]
python_version = "3.8"
check_untyped_defs = true
warn_unused_ignores = true
disallow_untyped_defs = false  # 段階的対応

# 既存の大規模ファイルは除外
[[tool.mypy.overrides]]
module = "main.performance_monitor"
ignore_errors = true
```

---

## コード品質

### Linting と Formatting

```bash
# Black でフォーマット（自動整形）
black main/ tests/

# Ruff で高速チェック
ruff check main/ --fix

# Pylint で詳細チェック
pylint main/

# 全チェック実行
./scripts/run_quality_checks.sh
```

### PEP 8 遵守

```python
# ✅ 良い例
class AvatarGenerator:
    """アバター生成器"""

    def __init__(self, config: Config):
        """初期化"""
        self.config = config
        self.cache = {}

    def generate(self, user_id: str) -> Avatar:
        """アバターを生成"""
        if user_id in self.cache:
            return self.cache[user_id]

        avatar = self._create_avatar(user_id)
        self.cache[user_id] = avatar
        return avatar

# ❌ 悪い例
class avatargen:  # 小文字で始まる
    def __init__(self,c):  # 短い名前
        self.c = c
        self.cache={}  # スペース不足
    def gen(self,uid):  # 短い名前
        if uid in self.cache:return self.cache[uid]  # 長すぎる行
        avatar=self._create(uid)  # スペース不足
        self.cache[uid]=avatar  # スペース不足
        return avatar
```

### 複雑度の測定

```bash
# Radon で複雑度を測定
radon cc main/ -a  # 平均複雑度も表示

# メトリクス表示
radon mi main/

# 詳細レポート
radon cc main/ --json > complexity.json
```

---

## 非同期プログラミング

### ベストプラクティス

```python
import asyncio
from main.async_base import AsyncBatch, AsyncPool

# ✅ 良い例: 非ブロッキング操作
async def fetch_multiple_users(user_ids: List[str]) -> List[User]:
    """複数ユーザーを並行取得"""
    batch = AsyncBatch(batch_size=10)

    async def fetch_user(user_id: str) -> User:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"/api/users/{user_id}") as resp:
                return await resp.json()

    return await batch.process(user_ids, fetch_user)

# ❌ 悪い例: ブロッキング操作
async def fetch_users_blocking(user_ids):
    """非ブロッキングではない"""
    import requests  # 同期ライブラリ

    results = []
    for user_id in user_ids:
        response = requests.get(f"/api/users/{user_id}")  # ブロッキング
        results.append(response.json())
    return results
```

### タイムアウト設定

```python
import asyncio
from main.async_base import async_timeout

@async_timeout(30.0)  # 30秒のタイムアウト
async def fetch_data(url: str) -> str:
    """タイムアウト付きで データを取得"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.text()

# 使用例
try:
    result = await fetch_data("https://example.com")
except asyncio.TimeoutError:
    logger.error("Request timeout")
```

---

## セキュリティ

### パスワードハッシング

```python
from main.integrated_security import SecurityManager

security = SecurityManager()

# パスワードをハッシュ化
hashed = security.hash_password("user_password")

# パスワード検証
is_valid = security.verify_password("user_password", hashed)
```

### 暗号化

```python
# 機密データを暗号化
plaintext = "sensitive_information"
encrypted = security.encrypt(plaintext)

# 復号化
decrypted = security.decrypt(encrypted)
assert decrypted == plaintext
```

### 認証・認可

```python
from fastapi import Depends, HTTPException

async def verify_token(token: str = Header(...)) -> Dict[str, Any]:
    """トークンを検証"""
    try:
        payload = security.verify_token(token)
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/protected")
async def protected_endpoint(user = Depends(verify_token)):
    """認証が必要なエンドポイント"""
    return {"user": user}
```

---

## パフォーマンス

### プロファイリング

```python
import cProfile
import pstats

def profile_function():
    """関数をプロファイリング"""
    profiler = cProfile.Profile()
    profiler.enable()

    # 計測対象の処理
    result = expensive_operation()

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative').print_stats(10)

    return result
```

### メモリ最適化

```python
# ✅ 良い例: ジェネレータで メモリ効率化
def process_large_file(filename: str):
    """大きなファイルを効率的に処理"""
    with open(filename) as f:
        for line in f:  # ジェネレータ
            yield process_line(line)

# ❌ 悪い例: 全行をメモリに読み込み
def process_large_file_bad(filename: str):
    """非効率な処理"""
    with open(filename) as f:
        lines = f.readlines()  # 全行をメモリに読み込む

    results = []
    for line in lines:
        results.append(process_line(line))
    return results
```

---

## チェックリスト

開発時に確認する項目:

- [ ] ロギングを実装（`get_logger()` を使用）
- [ ] テストを追加（最低でも関数ごと）
- [ ] 型ヒントを追加
- [ ] `mypy` で型チェック合格
- [ ] `black` でフォーマット合格
- [ ] `pylint` でスコア 8.0 以上
- [ ] Docstring を追加（PEP 257）
- [ ] 例外処理は `logger.exception()` を使用
- [ ] 非同期処理は非ブロッキング
- [ ] テストカバレッジ 70% 以上

---

## 参考リンク

- [Python Logging](https://docs.python.org/3/library/logging.html)
- [Pytest Documentation](https://docs.pytest.org/)
- [Mypy Documentation](https://mypy.readthedocs.io/)
- [PEP 8](https://pep8.org/)
- [PEP 257 - Docstring Conventions](https://peps.python.org/pep-0257/)
- [AsyncIO](https://docs.python.org/3/library/asyncio.html)

---

**版**: 1.0
**最終更新**: 2025-11-03

