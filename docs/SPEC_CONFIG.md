# 仕様書: Config

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/config.py`
**目的**: `SecurityConfig.validate()` の二重チェックバグ修正と型アノテーション修正。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-CF-01 | `SecurityConfig.validate()` が内部で `os.environ.get("ENVIRONMENT")` を再読みし、`Config(env="production")` が ENVIRONMENT 環境変数なしだと検証をスキップする | `ENVIRONMENT` 環境変数を設定しなくても `Config(env="production")` が失敗すべき場面で成功してしまう |
| GAP-CF-02 | `APIConfig.cors_origins: list = None` の型アノテーションが不正 | mypy/pyright が `None` を `list` として扱えない |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-CF-01 | `validate()` は呼ばれたら無条件に検証を行う（環境チェックは呼び元に委ねる） | 内部 `env = os.environ.get(...)` とその if を削除 |
| REQ-CF-02 | `cors_origins: Optional[list] = None` に修正 | `from typing import Optional` を使用（すでに import 済み） |

## 3. 仕様詳細

### `SecurityConfig.validate()` 修正 (REQ-CF-01)

Before:
```python
def validate(self):
    env = os.environ.get("ENVIRONMENT", "development")
    if env == "production":
        if self.secret_key == "change-me-in-production":
            raise ValueError(...)
```

After:
```python
def validate(self):
    if self.secret_key == "change-me-in-production":
        raise ValueError("SECRET_KEY must be set in production")
    if self.encryption_key == "change-me-in-production":
        raise ValueError("ENCRYPTION_KEY must be set in production")
```

`Config.__init__` は既に `if self.environment == "production": self.security.validate()` でガードしているため、`validate()` 内での二重チェックは不要かつ有害。

### `cors_origins` 型アノテーション (REQ-CF-02)

```python
cors_origins: Optional[list] = None
```

## 4. 受け入れ基準（テスト）

`tests/test_config.py`（stdlib unittest, 環境変数を汚染しない）:
- `Config()` はデフォルト設定で作成できる
- `Config(env="production")` は default secret_key で `ValueError`
- `SecurityConfig.validate()` は default secret_key で常に `ValueError`
- `cors_origins` は `None` から `__post_init__` で list に変換される
- `to_dict()` に `secret_key`/`password` が含まれない（情報漏洩防止）
- `Config.to_dict()` に必須キーが全て含まれる
