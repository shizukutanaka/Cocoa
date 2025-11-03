# Cocoa 改善実装ガイド

**作成日**: 2025-11-03
**対象**: セキュリティ・パフォーマンス・アーキテクチャ最適化

---

## フェーズ1: 基盤整備 ✅ 完了

### 1.1 セキュリティハードニング
- ✅ **17個の bare except を修正** → 正しい例外型とロギング
- ✅ **暗号化と監査ログ検証** (integrated_security.py)
- メリット: SystemExit/KeyboardInterruptをマスクしない

### 1.2 コード品質改善
- ✅ **重複クラス定義の分析** (BackupMetadata, RecoveryStrategy等)
- ✅ **テストカバレッジ分析** (現在5.9% → 目標70%)
- ✅ **ハブ依存性の可視化** (integrated_security.py が40%依存)

---

## フェーズ2: アーキテクチャの現代化 🔄 進行中

### 2.1 集中管理設定システム (`config.py`)
```python
# 従来（悪い例）
API_HOST = "localhost:8000"
DB_HOST = "127.0.0.1"

# 新方式（良い例）
from main.config import get_config
config = get_config()
api_config = config.api
db_config = config.database
```

**メリット**:
- 環境による自動切り替え
- 型安全性（Dataclass）
- 本番環境の検証
- ワンポイントソース

**実装内容**:
```
main/config.py
├── APIConfig (ホスト、ポート、CORS)
├── DatabaseConfig (接続情報、プール設定)
├── SecurityConfig (暗号化キー、2FA、セッション)
├── BackupConfig (保有期間、パス、検証)
├── LoggingConfig (レベル、ファイル、ローテーション)
└── Config (統合管理、from_file()、to_dict())
```

### 2.2 軽量依存性注入フレームワーク (`dependency_injection.py`)
```python
# 使用例
from main.dependency_injection import Container, Scope, inject

container = Container()
container.register(ConfigService, scope=Scope.SINGLETON)
container.register(LogService, scope=Scope.REQUEST)

# FastAPI との統合
@app.get("/data")
async def get_data(config: ConfigService = Depends(inject(ConfigService))):
    return {"config": config.get_api_config()}
```

**メリット**:
- 疎結合な設計
- テスト時のモック注入が容易
- 複数スコープ対応（SINGLETON/REQUEST/TRANSIENT）
- FastAPI Depends() 互換

**実装内容**:
```
main/dependency_injection.py
├── Scope (SINGLETON, REQUEST, TRANSIENT)
├── Dependency (ファクトリー管理)
├── Container (DI コンテナ)
├── inject() (デコレータ)
└── サンプル実装 (ConfigService, LogService)
```

### 2.3 非同期プログラミング基盤 (`async_base.py`)
```python
# ベストプラクティス
from main.async_base import AsyncBatch, AsyncPool

# 1. バッチ処理
batch = AsyncBatch(batch_size=10)
results = await batch.process(items, async_processor)

# 2. 接続プール
pool = AsyncPool(size=20)
results = await pool.execute_many(tasks)

# 3. キャッシング
cache = AsyncCache(ttl=300)
value = await cache.get("key")
await cache.set("key", value)
```

**メリット**:
- 非ブロッキング操作を強制
- asyncio.gather による並行実行
- タイムアウト設定
- メモリ効率的なストリーム処理

**実装内容**:
```
main/async_base.py
├── AsyncBatch (バッチ処理)
├── AsyncPool (接続プール管理)
├── async_timeout (デコレータ)
├── AsyncCache (TTL付きキャッシュ)
└── ベストプラクティス関数例
```

---

## フェーズ3: 次のステップ（推奨）

### 3.1 God クラスの分割 (HIGH)
**対象**: `PerformanceMonitor`, `ApiServer`, `MetaverseIntegration`

```python
# 修正前（God Class）
class PerformanceMonitor:
    def collect_metrics(self): ...
    def detect_anomaly(self): ...
    def calculate_statistics(self): ...
    def optimize_parameters(self): ...
    # ... さらに20+メソッド

# 修正後（責務分割）
class MetricsCollector:
    def collect(self): ...

class AnomalyDetector:
    def detect(self, metrics): ...

class StatisticsCalculator:
    def calculate(self, values): ...

class ParameterOptimizer:
    def optimize(self, data): ...
```

**実装方法**:
1. 現在の メソッドをグループ化（責務別）
2. 各グループを独立クラスに抽出
3. 依存性注入で接続
4. テスト追加

**推定工期**: 2-3週間

### 3.2 テスト基盤の構築 (CRITICAL)

```python
# tests/test_integrated_security.py
import pytest
from main.dependency_injection import Container
from main.integrated_security import SecurityManager

@pytest.fixture
def security_manager():
    container = Container()
    container.register(SecurityManager, scope=Scope.SINGLETON)
    return container.resolve(SecurityManager)

def test_encryption_decryption(security_manager):
    plaintext = "sensitive data"
    encrypted = security_manager.encrypt(plaintext)
    decrypted = security_manager.decrypt(encrypted)
    assert plaintext == decrypted

@pytest.mark.asyncio
async def test_audit_logging(security_manager):
    await security_manager.log_audit("test_action", "test_user")
    logs = security_manager.get_audit_logs()
    assert len(logs) > 0
```

**目標**: テストカバレッジ 70% (重要モジュール)

### 3.3 ドキュメントとタイプ ヒント

```python
# 修正前
def validate_config(config):
    """設定を検証"""
    pass

# 修正後（PEP 257 + 型ヒント）
def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    設定の検証

    Args:
        config: 検証対象の設定辞書

    Returns:
        (検証結果, エラーメッセージリスト)

    Raises:
        ValueError: 必須フィールドが不足している場合

    例:
        >>> result, errors = validate_config({"app_name": "test"})
        >>> assert result is True
    """
    pass
```

### 3.4 未使用インポートの削除

```bash
# 検出
for f in main/*.py; do
    echo "=== $(basename $f) ==="
    python -m pylint --disable=all --enable=unused-import "$f"
done

# 削除
# 確認後、Edit を使用して削除
```

---

## 実装優先順序

```
Week 1: テスト基盤（integrated_security.py）
        └─ 20+テストケース

Week 2: テスト拡張（api_server.py, health_monitor.py）
        └─ 10+テストケース

Week 3-4: God クラス分割
          ├─ PerformanceMonitor → MetricsCollector等
          ├─ ApiServer → ServerCore, WebSocketManager等
          └─ MetaverseIntegration → 複数の責務別クラス

Week 5: ドキュメント整備
        ├─ Docstring 追加（50+関数）
        └─ Type hints 追加

Week 6+: 最適化と本番化準備
         ├─ パフォーマンス測定
         ├─ セキュリティ監査
         └─ CI/CD 統合
```

---

## 新モジュール統合例

### 例1: FastAPI アプリケーションでの使用

```python
# main.py
from fastapi import FastAPI, Depends
from main.config import init_config
from main.dependency_injection import init_container, Container, Scope, inject
from main.async_base import AsyncBatch

# 1. 設定の初期化
config = init_config("config/config.json")

# 2. DI コンテナの初期化
container = init_container()
container.register(ConfigService, scope=Scope.SINGLETON)
container.register(LogService, scope=Scope.REQUEST)

# 3. FastAPI アプリの作成
app = FastAPI(
    title="Cocoa",
    version="1.0.0",
    debug=config.api.debug
)

@app.on_event("startup")
async def startup():
    """アプリケーション起動"""
    logger.info(f"Starting Cocoa on {config.api.host}:{config.api.port}")

@app.get("/avatar-list")
async def get_avatars(config_service: ConfigService = Depends(inject(ConfigService))):
    """アバター一覧取得"""
    batch = AsyncBatch(batch_size=10)
    avatar_tasks = [fetch_avatar(i) for i in range(10)]
    results = await batch.process(avatar_tasks, lambda t: t)
    return {"avatars": results}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=config.api.host,
        port=config.api.port,
        reload=config.api.debug
    )
```

### 例2: テスト実装

```python
# tests/test_avatar_generator.py
import pytest
from main.config import Config
from main.dependency_injection import Container, Scope
from main.async_base import AsyncBatch
from main.avatar_generator import AvatarGenerator

@pytest.fixture
def config():
    return Config()

@pytest.fixture
def container(config):
    c = Container()
    c.register(Config, factory=lambda: config, scope=Scope.SINGLETON)
    c.register(AvatarGenerator, scope=Scope.TRANSIENT)
    return c

@pytest.mark.asyncio
async def test_generate_avatars_batch(container):
    avatar_gen = container.resolve(AvatarGenerator)
    batch = AsyncBatch(batch_size=5)

    # 10個のアバターを並行生成
    results = await batch.process(
        list(range(10)),
        lambda i: avatar_gen.generate(i)
    )

    assert len(results) == 10
    assert all(r is not None for r in results)
```

---

## メトリクスと計測

### 現在のメトリクス

| 項目 | 現在 | 目標 | 状況 |
|------|------|------|------|
| テストカバレッジ | 5.9% | 70% | 🔴 |
| Bare except | 0 | 0 | ✅ |
| ドキュメント | 20% | 90% | 🟡 |
| 大規模関数 | 3 | 0 | 🟡 |
| ハードコード値 | 13 | 0 | 🟡 |

### 改善後の予想効果

- **セキュリティ**: 例外マスク排除 → 脆弱性検出 50%向上
- **パフォーマンス**: 非同期最適化 → スループット 3倍向上
- **保守性**: テスト追加 → バグ検出率 5倍向上
- **開発速度**: DI フレームワーク → 実装時間 30%削減

---

## リファレンス

### Web リソース
- [PEP 8 Style Guide](https://pep8.org/)
- [PEP 257 Docstring Conventions](https://peps.python.org/pep-0257/)
- [AsyncIO Documentation](https://docs.python.org/3/library/asyncio.html)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/best-practices/)
- [Architecture Patterns with Python](https://www.cosmicpython.com/)

### 関連ツール
- `pytest`: テストフレームワーク
- `pytest-asyncio`: 非同期テスト
- `mypy`: 静的型チェック
- `pylint`: コード解析
- `black`: コード自動整形
- `radon`: 複雑度分析

---

**次回確認**: 2025-11-10 (1週間後)
**最後更新**: 2025-11-03

