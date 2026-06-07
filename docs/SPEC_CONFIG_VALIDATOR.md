# 仕様書: ConfigValidator

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/config_validator.py`
**目的**: デッドコードの活性化とブール/整数型混同バグの修正。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-CV-01 | `_validate_password_policy()` が `_apply_post_validation()` から呼ばれていない | billing/notification/rate_limiting のクロスフィールド検証がすべて実行されない（デッドコード） |
| GAP-CV-02 | `_validate_field()` の integer 型チェック: `isinstance(True, int)` は Python で `True`（bool は int のサブクラス）| `{"port": true}` が integer として通過してしまう |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-CV-01 | `_apply_post_validation()` の末尾で `_validate_password_policy()` を呼ぶ | `security_cfg = original_config.get("security") or {}; self._validate_password_policy(security_cfg, errors, warnings, original_config, validated_config)` |
| REQ-CV-02 | integer 型チェックで bool を除外 | `isinstance(value, int) and not isinstance(value, bool)` |

## 3. 仕様詳細

### `_apply_post_validation()` 末尾への呼び出し追加 (REQ-CV-01)

`_apply_post_validation` の最終行（`max_login_attempts` チェックの後）に追加:

```python
# billing / notification / rate_limiting のクロスフィールド検証
security_cfg = original_config.get("security")
if not isinstance(security_cfg, dict):
    security_cfg = {}
self._validate_password_policy(security_cfg, errors, warnings, original_config, validated_config)
```

### integer 型チェックの修正 (REQ-CV-02)

`_validate_field()` 内 `elif field_type == "integer":` ブロック:

```python
elif field_type == "integer":
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(...)
```

## 4. 受け入れ基準（テスト）

`tests/test_config_validator.py`（stdlib unittest, ファイル不要: `validate_from_dict` を使用）:
- 必須フィールドが欠けている場合にエラー
- 文字列フィールドに整数を渡すとエラー
- integer フィールドに bool (`True`) を渡すとエラー (REQ-CV-02)
- pattern チェック (version: `"1.0.0"` は OK, `"1.0"` はエラー)
- allowed_values チェック (language: `"fr"` はエラー)
- rate_limiting クロスフィールド検証 (minute > hour でエラー) (REQ-CV-01 activation)
- 有効な設定は `valid: True` を返す
