# Cocoa開発者ガイド

## 目次

- [環境構築](#環境構築)
- [プロジェクト構造](#プロジェクト構造)
- [開発ワークフロー](#開発ワークフロー)
- [アーキテクチャ](#アーキテクチャ)
- [コーディング規約](#コーディング規約)
- [テスト](#テスト)
- [デバッグ](#デバッグ)
- [パフォーマンス](#パフォーマンス)
- [セキュリティ](#セキュリティ)
- [デプロイメント](#デプロイメント)
- [トラブルシューティング](#トラブルシューティング)

## 環境構築

### 必要な環境

- **Python**: 3.9以上
- **Node.js**: 16以上（フロントエンド開発の場合）
- **Git**: 最新版
- **エディタ**: VS Code推奨

### 開発環境セットアップ

```bash
# リポジトリクローン
git clone <REPOSITORY_URL>
cd cocoa

# 仮想環境作成
python -m venv venv

# 仮想環境アクティベート（Windows）
venv\Scripts\activate
# 仮想環境アクティベート（macOS/Linux）
source venv/bin/activate

# 依存関係インストール
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 開発用設定ファイル作成
cp config/config.example.json config/config.json

# データベース初期化
python scripts/migrate_to_database.py

# セキュリティ設定
python setup_security.py

# 開発サーバー起動
python main/web_admin_improved.py
```

### VS Code設定

`.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests/"],
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    ".pytest_cache": true
  }
}
```

### 開発用依存関係

`requirements-dev.txt`:
```
# テスト
pytest==7.4.3
pytest-cov==4.1.0
pytest-asyncio==0.21.1
pytest-mock==3.12.0

# リンティング・フォーマット
black==23.11.0
flake8==6.1.0
pylint==3.0.2
mypy==1.7.1
isort==5.12.0

# ドキュメント
sphinx==7.2.6
sphinx-rtd-theme==1.3.0

# デバッグ
pdb++==0.10.3
ipython==8.17.2

# プロファイリング
line_profiler==4.1.1
memory_profiler==0.61.0
```

## プロジェクト構造

```
cocoa/
├── main/                          # メインアプリケーション
│   ├── main.py                    # アプリケーション起動点
│   ├── web_admin_improved.py      # Web管理インターフェース
│   ├── integrated_security.py     # 統合セキュリティ
│   ├── performance_monitor.py     # パフォーマンス監視
│   ├── disaster_recovery.py       # バックアップと復旧
│   ├── logging_manager.py         # ログ管理
│   ├── notification_system.py     # 通知システム
│   ├── preset_manager.py          # プリセット管理
│   ├── health_monitor.py          # ヘルスチェック
│   ├── config_validator.py        # 設定検証
│   ├── parameters.py              # パラメータ定義
│   └── i18n.py                    # 国際化ユーティリティ
├── config/                       # 設定ファイル
│   ├── config.json              # メイン設定
│   ├── database.json            # データベース設定
│   └── security.json            # セキュリティ設定
├── tests/                       # テストコード
│   ├── __init__.py
│   ├── test_security.py         # セキュリティテスト
│   ├── test_performance.py      # パフォーマンステスト
│   ├── test_database.py         # データベーステスト
│   └── fixtures/                # テスト用データ
├── docs/                        # ドキュメント
│   ├── API_REFERENCE.md         # API リファレンス
│   ├── DEVELOPER_GUIDE.md       # 開発者ガイド
│   ├── CONFIGURATION.md         # 設定ガイド
│   └── TROUBLESHOOTING.md       # トラブルシューティング
├── scripts/                     # ユーティリティスクリプト
│   ├── migrate_to_database.py   # データ移行ユーティリティ
│   ├── run_performance_tests.py # パフォーマンステスト実行
│   └── perf_log_viewer.py       # パフォーマンスログ分析
├── locales/                     # 多言語リソース
│   ├── en.json                  # 英語
│   ├── ja.json                  # 日本語
│   └── zh.json                  # 中国語
├── requirements.txt             # 依存関係一覧
├── run_tests.py                 # テストランナー
├── run_tests_new.py             # テストランナー(代替)
├── setup/                      # セットアップスクリプト
│   ├── setup_security.py       # セキュリティ初期化
│   └── ...
├── docs/                       # ドキュメント
│   ├── CONFIGURATION.md
│   ├── TROUBLESHOOTING.md
│   └── ...
├── locales/                    # 多言語リソース
│   ├── en.json
│   ├── ja.json
│   └── ...
└── tests/                      # テストコード
```

## 開発ワークフロー

### ブランチ戦略

```
main
├── develop                     # 開発統合ブランチ
├── feature/new-preset-editor  # 機能開発ブランチ
├── bugfix/security-fix        # バグ修正ブランチ
├── hotfix/critical-patch      # 緊急修正ブランチ
└── release/v2.1.0            # リリースブランチ
```

### 開発プロセス

1. **Issue作成**: GitHub Issuesで作業項目を管理
2. **ブランチ作成**: `feature/issue-123-description`形式
3. **開発**: コーディング規約に従って実装
4. **テスト**: 単体テスト・統合テスト実行
5. **レビュー**: Pull Request作成・レビュー
6. **マージ**: レビュー完了後にdevelopブランチへマージ

### Git Hooks

`.git/hooks/pre-commit`:
```bash
#!/bin/sh
# コードフォーマットとリンティング
black --check .
flake8 .
mypy main/
pytest tests/ -x
```

## アーキテクチャ

### システム構成

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                       │
├─────────────────────────────────────────────────────────────┤
│  Web UI (Flask)  │  REST API  │  WebSocket API  │  CLI      │
├─────────────────────────────────────────────────────────────┤
│                    Business Logic Layer                     │
├─────────────────────────────────────────────────────────────┤
│  Preset Manager  │  Avatar Manager  │  Security Manager     │
│  Performance     │  I18n Manager    │  Backup Manager       │
├─────────────────────────────────────────────────────────────┤
│                    Data Access Layer                        │
├─────────────────────────────────────────────────────────────┤
│  Database Manager  │  Cache Manager  │  File System         │
├─────────────────────────────────────────────────────────────┤
│                    Infrastructure Layer                     │
├─────────────────────────────────────────────────────────────┤
│  SQLite/PostgreSQL/MySQL  │  Redis (optional)  │  File I/O  │
└─────────────────────────────────────────────────────────────┘
```

### デザインパターン

#### 1. Singleton Pattern
```python
class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

#### 2. Factory Pattern
```python
class DatabaseFactory:
    @staticmethod
    def create_manager(db_type: DatabaseType) -> DatabaseManager:
        if db_type == DatabaseType.SQLITE:
            return SQLiteManager()
        elif db_type == DatabaseType.POSTGRESQL:
            return PostgreSQLManager()
        # ...
```

#### 3. Observer Pattern
```python
class PresetManager:
    def __init__(self):
        self._observers = []

    def add_observer(self, observer):
        self._observers.append(observer)

    def notify_observers(self, event):
        for observer in self._observers:
            observer.on_preset_changed(event)
```

### 依存性注入

```python
from typing import Protocol

class DatabaseInterface(Protocol):
    def save_preset(self, preset: Preset) -> bool: ...
    def load_preset(self, preset_id: str) -> Preset: ...

class PresetService:
    def __init__(self, db: DatabaseInterface):
        self.db = db

    def create_preset(self, data: dict) -> Preset:
        preset = Preset(data)
        self.db.save_preset(preset)
        return preset
```

## コーディング規約

### Python PEP 8準拠

```python
# Good: クラス名はPascalCase
class PresetManager:
    pass

# Good: 関数名はsnake_case
def create_preset(preset_data: dict) -> Preset:
    pass

# Good: 定数は大文字
MAX_PRESET_SIZE = 1024 * 1024

# Good: 型ヒント使用
def process_presets(presets: List[Preset]) -> Dict[str, Any]:
    pass
```

### ドキュメンテーション

```python
def create_preset(name: str, parameters: Dict[str, Any]) -> Preset:
    """プリセットを作成します。

    Args:
        name: プリセット名
        parameters: プリセットパラメータ辞書

    Returns:
        作成されたPresetオブジェクト

    Raises:
        ValidationError: パラメータが無効な場合
        DatabaseError: データベース操作に失敗した場合

    Example:
        >>> preset = create_preset("カジュアル", {"hair_color": "#000"})
        >>> print(preset.name)
        カジュアル
    """
    pass
```

### エラーハンドリング

```python
# Good: 具体的な例外を使用
try:
    preset = load_preset(preset_id)
except PresetNotFoundError:
    logger.warning(f"プリセットが見つかりません: {preset_id}")
    return None
except DatabaseError as e:
    logger.error(f"データベースエラー: {e}")
    raise

# Good: リソースの適切な管理
with open(file_path, 'r') as f:
    data = f.read()

# Good: 複数の例外をまとめて処理
try:
    result = risky_operation()
except (NetworkError, TimeoutError) as e:
    logger.error(f"通信エラー: {e}")
    raise ServiceUnavailableError()
```

### ログ記録

```python
import logging

logger = logging.getLogger(__name__)

def process_avatar(avatar_id: str):
    logger.info(f"アバター処理開始: {avatar_id}")

    try:
        # 処理実行
        result = expensive_operation(avatar_id)
        logger.info(f"アバター処理完了: {avatar_id}")
        return result
    except Exception as e:
        logger.error(f"アバター処理エラー: {avatar_id} - {e}", exc_info=True)
        raise
```

## テスト

### テスト構造

```python
# tests/test_preset_manager.py
import pytest
from unittest.mock import Mock, patch
from main.preset_manager import PresetManager
from main.database_manager import DatabaseManager

class TestPresetManager:
    """PresetManagerのテストクラス"""

    @pytest.fixture
    def mock_db(self):
        """モックデータベース"""
        return Mock(spec=DatabaseManager)

    @pytest.fixture
    def preset_manager(self, mock_db):
        """テスト用PresetManager"""
        return PresetManager(mock_db)

    def test_create_preset_success(self, preset_manager, mock_db):
        """プリセット作成成功テスト"""
        # Given
        preset_data = {"name": "テストプリセット", "parameters": {}}
        mock_db.save_preset.return_value = True

        # When
        result = preset_manager.create_preset(preset_data)

        # Then
        assert result is not None
        assert result.name == "テストプリセット"
        mock_db.save_preset.assert_called_once()

    def test_create_preset_validation_error(self, preset_manager):
        """プリセット作成バリデーションエラーテスト"""
        # Given
        invalid_data = {"parameters": {}}  # nameがない

        # When & Then
        with pytest.raises(ValidationError):
            preset_manager.create_preset(invalid_data)

    @patch('main.preset_manager.datetime')
    def test_preset_timestamp(self, mock_datetime, preset_manager, mock_db):
        """プリセットタイムスタンプテスト"""
        # Given
        fixed_time = datetime(2024, 1, 15, 12, 0, 0)
        mock_datetime.now.return_value = fixed_time

        # When
        preset = preset_manager.create_preset({"name": "test"})

        # Then
        assert preset.created_at == fixed_time
```

### パフォーマンステスト

```python
# tests/test_performance.py
import pytest
import time
from main.performance_tester import CocoaPerformanceTester

class TestPerformance:
    """パフォーマンステスト"""

    def test_preset_creation_performance(self):
        """プリセット作成のパフォーマンステスト"""
        tester = CocoaPerformanceTester()

        start_time = time.time()

        # 100個のプリセットを作成
        for i in range(100):
            tester.create_test_preset(f"preset_{i}")

        end_time = time.time()
        duration = end_time - start_time

        # 100個のプリセット作成が5秒以内に完了することを確認
        assert duration < 5.0, f"プリセット作成が遅すぎます: {duration}秒"

    @pytest.mark.slow
    def test_memory_usage_under_load(self):
        """負荷時のメモリ使用量テスト"""
        import psutil
        import gc

        process = psutil.Process()
        initial_memory = process.memory_info().rss

        # 大量のデータを処理
        for i in range(1000):
            large_data = [j for j in range(1000)]
            # データ処理

        gc.collect()
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # メモリ増加が100MB以下であることを確認
        assert memory_increase < 100 * 1024 * 1024
```

### テスト実行

```bash
# 全テスト実行
pytest

# カバレッジ付きテスト実行
pytest --cov=main --cov-report=html

# 特定のテストファイル実行
pytest tests/test_preset_manager.py

# 特定のテストクラス実行
pytest tests/test_preset_manager.py::TestPresetManager

# 特定のテストメソッド実行
pytest tests/test_preset_manager.py::TestPresetManager::test_create_preset_success

# 並列テスト実行
pytest -n auto

# 遅いテストをスキップ
pytest -m "not slow"
```

## デバッグ

### デバッグ環境設定

```python
# main/debug_config.py
import logging
import sys

def setup_debug_logging():
    """デバッグ用ログ設定"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('debug.log')
        ]
    )

def enable_debug_mode():
    """デバッグモード有効化"""
    import os
    os.environ['FLASK_DEBUG'] = '1'
    os.environ['COCOA_DEBUG'] = '1'
```

### デバッグ用ツール

```python
# デバッガー起動
import pdb; pdb.set_trace()

# 条件付きデバッガー
if preset_id == "problematic_preset":
    import pdb; pdb.set_trace()

# プロファイリング
from line_profiler import LineProfiler
profiler = LineProfiler()
profiler.add_function(expensive_function)
profiler.enable_by_count()
expensive_function()
profiler.print_stats()
```

### メモリデバッグ

```python
# メモリ使用量監視
import tracemalloc
tracemalloc.start()

# 処理実行
process_large_data()

# メモリ使用量確認
current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 1024 / 1024:.1f} MB")
print(f"Peak memory usage: {peak / 1024 / 1024:.1f} MB")
tracemalloc.stop()
```

## パフォーマンス

### プロファイリング

```python
# CPUプロファイリング
import cProfile
import pstats

def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()

    # 測定対象の処理
    expensive_operation()

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)

# メモリプロファイリング
from memory_profiler import profile

@profile
def memory_intensive_function():
    large_list = [i for i in range(1000000)]
    return large_list
```

### 最適化手法

#### 1. キャッシング

```python
from functools import lru_cache
import time

@lru_cache(maxsize=128)
def expensive_calculation(param):
    time.sleep(1)  # 重い処理をシミュレート
    return param * 2

# 使用例
result1 = expensive_calculation(5)  # 1秒かかる
result2 = expensive_calculation(5)  # キャッシュから即座に返る
```

#### 2. 非同期処理

```python
import asyncio
import aiohttp

async def fetch_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

async def process_multiple_urls(urls):
    tasks = [fetch_data(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return results
```

#### 3. バッチ処理

```python
def process_presets_batch(preset_ids: List[str], batch_size: int = 100):
    """プリセットをバッチ処理"""
    for i in range(0, len(preset_ids), batch_size):
        batch = preset_ids[i:i + batch_size]

        # データベースから一括取得
        presets = db.load_presets_batch(batch)

        # 一括処理
        results = [process_preset(preset) for preset in presets]

        # 一括保存
        db.save_presets_batch(results)
```

### データベース最適化

```python
# インデックス作成
def create_database_indexes():
    """パフォーマンス向上のためのインデックス作成"""
    indexes = [
        "CREATE INDEX idx_presets_name ON presets(name)",
        "CREATE INDEX idx_presets_category ON presets(category)",
        "CREATE INDEX idx_presets_created_at ON presets(created_at)",
        "CREATE INDEX idx_audit_log_timestamp ON audit_log(timestamp)"
    ]

    for index_sql in indexes:
        db.execute_query(index_sql)

# クエリ最適化
def optimized_preset_search(query: str, category: str = None):
    """最適化されたプリセット検索"""
    sql_parts = ["SELECT * FROM presets WHERE name LIKE ?"]
    params = [f"%{query}%"]

    if category:
        sql_parts.append("AND category = ?")
        params.append(category)

    sql_parts.append("ORDER BY created_at DESC LIMIT 50")

    sql = " ".join(sql_parts)
    return db.execute_query(sql, params)
```

## セキュリティ

### セキュアコーディング

```python
# 入力値検証
import re
from typing import Union

def validate_preset_name(name: str) -> bool:
    """プリセット名のバリデーション"""
    if not isinstance(name, str):
        return False

    if len(name) < 1 or len(name) > 100:
        return False

    # 危険な文字を除外
    dangerous_chars = ['<', '>', '"', "'", '&', '\\', '/', '\n', '\r']
    if any(char in name for char in dangerous_chars):
        return False

    return True

# SQLインジェクション対策
def safe_database_query(query: str, params: tuple):
    """安全なデータベースクエリ実行"""
    # パラメータ化クエリを使用
    cursor = db.cursor()
    cursor.execute(query, params)
    return cursor.fetchall()

# XSS対策
import html

def escape_html_output(text: str) -> str:
    """HTML出力時のエスケープ"""
    return html.escape(text)
```

### 認証・認可

```python
from functools import wraps
import jwt
from flask import request, jsonify

def require_auth(f):
    """認証必須デコレータ"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'error': '認証が必要です'}), 401

        try:
            # Bearer tokenの場合
            if token.startswith('Bearer '):
                token = token[7:]

            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            request.user_id = payload['user_id']

        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'トークンが期限切れです'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': '無効なトークンです'}), 401

        return f(*args, **kwargs)

    return decorated_function

def require_permission(permission: str):
    """権限チェックデコレータ"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_permissions = get_user_permissions(request.user_id)

            if permission not in user_permissions:
                return jsonify({'error': '権限がありません'}), 403

            return f(*args, **kwargs)

        return decorated_function
    return decorator
```

### セキュリティ監査

```python
def security_audit():
    """セキュリティ監査実行"""
    audit_results = []

    # 1. パスワード強度チェック
    weak_passwords = check_weak_passwords()
    if weak_passwords:
        audit_results.append({
            'level': 'HIGH',
            'issue': '弱いパスワードが検出されました',
            'details': weak_passwords
        })

    # 2. 不正なファイルアクセス検出
    suspicious_access = detect_suspicious_file_access()
    if suspicious_access:
        audit_results.append({
            'level': 'MEDIUM',
            'issue': '不審なファイルアクセスが検出されました',
            'details': suspicious_access
        })

    # 3. SQLインジェクション試行検出
    sql_injection_attempts = detect_sql_injection_attempts()
    if sql_injection_attempts:
        audit_results.append({
            'level': 'HIGH',
            'issue': 'SQLインジェクション試行が検出されました',
            'details': sql_injection_attempts
        })

    return audit_results
```

## デプロイメント

### 環境別設定

```python
# config/environments.py
import os

class Config:
    """基本設定クラス"""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    DATABASE_URL = os.environ.get('DATABASE_URL')

class DevelopmentConfig(Config):
    """開発環境設定"""
    DEBUG = True
    DATABASE_URL = 'sqlite:///cocoa_dev.db'
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    """本番環境設定"""
    DEBUG = False
    DATABASE_URL = os.environ.get('DATABASE_URL')
    LOG_LEVEL = 'WARNING'
    SESSION_SECURE = True

class TestingConfig(Config):
    """テスト環境設定"""
    TESTING = True
    DATABASE_URL = 'sqlite:///cocoa_test.db'
    WTF_CSRF_ENABLED = False

def get_config():
    """環境に応じた設定を取得"""
    env = os.environ.get('FLASK_ENV', 'development')

    config_map = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'testing': TestingConfig
    }

    return config_map.get(env, DevelopmentConfig)
```

### Docker化

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# システム依存関係
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコード
COPY . .

# 非rootユーザー作成
RUN useradd --create-home --shell /bin/bash cocoa
RUN chown -R cocoa:cocoa /app
USER cocoa

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/status || exit 1

EXPOSE 8080

CMD ["python", "main/web_admin_improved.py"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  cocoa:
    build: .
    ports:
      - "8080:8080"
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=postgresql://user:pass@db:5432/cocoa
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - db
      - redis
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=cocoa
      - POSTGRES_USER=cocoa
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Lint with flake8
      run: |
        flake8 main/ tests/

    - name: Type check with mypy
      run: |
        mypy main/

    - name: Test with pytest
      run: |
        pytest --cov=main --cov-report=xml

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3

  security:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Run security scan
      run: |
        pip install bandit safety
        bandit -r main/
        safety check

    - name: Run CodeQL Analysis
      uses: github/codeql-action/analyze@v2

  deploy:
    needs: [test, security]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
    - uses: actions/checkout@v4

    - name: Build Docker image
      run: |
        docker build -t cocoa:${{ github.sha }} .

    - name: Deploy to production
      run: |
        # デプロイスクリプト実行
        ./scripts/deploy.sh
```

## 🔧 トラブルシューティング

### よくある問題

#### 1. データベース接続エラー

```python
# 問題: "could not connect to server"
# 解決策:
def diagnose_database_connection():
    """データベース接続診断"""
    try:
        # 接続テスト
        db.execute_query("SELECT 1")
        print("データベース接続正常")

    except ConnectionError as e:
        print(f"接続エラー: {e}")
        print("確認項目:")
        print("- データベースサーバーが起動しているか")
        print("- 接続情報（ホスト、ポート、認証情報）が正しいか")
        print("- ファイアウォールが接続をブロックしていないか")

    except AuthenticationError as e:
        print(f"認証エラー: {e}")
        print("確認項目:")
        print("- ユーザー名・パスワードが正しいか")
        print("- データベースユーザーに適切な権限があるか")
```

#### 2. メモリ不足

```python
def diagnose_memory_usage():
    """メモリ使用状況診断"""
    import psutil

    memory = psutil.virtual_memory()

    print(f"総メモリ: {memory.total / 1024**3:.1f}GB")
    print(f"使用メモリ: {memory.used / 1024**3:.1f}GB")
    print(f"使用率: {memory.percent:.1f}%")

    if memory.percent > 90:
        print("メモリ使用率が高すぎます")
        print("対策:")
        print("- 不要なプロセスを終了")
        print("- キャッシュサイズを縮小")
        print("- メモリ増設を検討")
```

#### 3. パフォーマンス問題

```python
def diagnose_performance():
    """パフォーマンス診断"""
    import time

    # レスポンス時間測定
    start_time = time.time()
    test_database_query()
    db_response_time = time.time() - start_time

    if db_response_time > 1.0:
        print(f"データベースクエリが遅い: {db_response_time:.2f}秒")
        print("対策:")
        print("- インデックス作成")
        print("- クエリ最適化")
        print("- 接続プール調整")
```

### ログ分析

```python
def analyze_error_logs():
    """エラーログ分析"""
    import re
    from collections import Counter

    error_patterns = [
        r'ERROR.*?(Exception|Error): (.+)',
        r'WARNING.*?Rate limit exceeded for (.+)',
        r'CRITICAL.*?Database connection failed'
    ]

    error_counts = Counter()

    with open('logs/cocoa.log', 'r') as f:
        for line in f:
            for pattern in error_patterns:
                match = re.search(pattern, line)
                if match:
                    error_type = match.group(1) if match.group(1) else "Unknown"
                    error_counts[error_type] += 1

    print("エラー統計:")
    for error_type, count in error_counts.most_common():
        print(f"- {error_type}: {count}回")
```

### 診断スクリプト

```python
#!/usr/bin/env python3
"""
Cocoa診断スクリプト
システムの健全性をチェックします
"""

def run_full_diagnosis():
    """総合診断実行"""
    print("🔍 Cocoa システム診断開始")
    print("=" * 50)

    # システムリソース
    print("\n📊 システムリソース")
    diagnose_system_resources()

    # データベース接続
    print("\n💾 データベース接続")
    diagnose_database_connection()

    # セキュリティ
    print("\n🔒 セキュリティ状態")
    diagnose_security()

    # パフォーマンス
    print("\n⚡ パフォーマンス")
    diagnose_performance()

    print("\n✅ 診断完了")

if __name__ == "__main__":
    run_full_diagnosis()
```

---

## 📚 参考資料

- [Python公式ドキュメント](https://docs.python.org/3/)
- [Flask公式ドキュメント](https://flask.palletsprojects.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Docker Documentation](https://docs.docker.com/)

## 🤝 コントリビューション

プロジェクトへの貢献を歓迎します！詳細は[CONTRIBUTING.md](CONTRIBUTING.md)をご確認ください。

## 📞 サポート

- **社内サポート**: 運用担当者が案内するサポート窓口をご利用ください
- **ドキュメント**: `docs/` ディレクトリ内の各種ガイドを参照
- **チームチャット**: 導入環境で指定されたサポート掲示板やチャットツールを活用してください