# 仕様書: SecretManager

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/secret_manager.py`
**目的**: `EnvironmentSecretManager` の一貫性バグと `get_secret_manager` のサイレントフォールバックを修正。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-SM-01 | `EnvironmentSecretManager.list_secrets()` が `COCOA_` プレフィックスの env var だけを返す。`set_secret('MY_KEY', 'v')` しても `list_secrets()` に現れない | set/list の一貫性が壊れている |
| GAP-SM-02 | `get_secret_manager('unknown_provider')` が `SecretProvider.ENVIRONMENT` にサイレントフォールバックする | 誤ったプロバイダー名のスペルミスが検出されない |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-SM-01 | `list_secrets()` は `_secrets` dict の全キーを返す | `return list(self._secrets.keys())` |
| REQ-SM-02 | `get_secret_manager(provider)` は未知のプロバイダー名で `ValueError` を送出 | デフォルト値なしで `provider_map.get(provider.lower())` + None ガード |

## 3. 仕様詳細

### `EnvironmentSecretManager.list_secrets()` (REQ-SM-01)
```python
def list_secrets(self) -> List[str]:
    return list(self._secrets.keys())
```
- `set_secret(name, val)` は `_secrets[name] = val` を設定するため、
  `list_secrets()` はそのキーを返す必要がある。
- env var に依存しないため、テストが独立して行える。

### `get_secret_manager()` (REQ-SM-02)
```python
provider_enum = provider_map.get(provider.lower())
if provider_enum is None:
    raise ValueError(
        f"Unknown secret provider: {provider!r}. "
        f"Must be one of {list(provider_map.keys())}"
    )
return SecretManagerFactory.create(provider_enum)
```

## 4. 受け入れ基準（テスト）

`tests/test_secret_manager.py`（stdlib unittest, env 汚染なし):
- `set_secret` → `get_secret` ラウンドトリップ
- `set_secret` → `list_secrets` に含まれる（REQ-SM-01 regression）
- `delete_secret` → `get_secret` が KeyError
- `rotate_secret` → 新しい値が `get_secret` で返る
- `get_secret_manager('env')` → `EnvironmentSecretManager`
- `get_secret_manager('bad')` → `ValueError` (REQ-SM-02 regression)
