# 仕様書: 集中管理ロギング設定

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/logging_config.py`
**目的**: 無効レベル指定の沈黙・utcnow 非推奨を修正し、要件を明文化する。

## 1. 現状とギャップ

- **GAP-1**: **無効なレベル文字列が警告なしに受け入れられる**: `configure_logging(level="VERBOSE")`
  を呼んでも `getattr(logging, "VERBOSE", logging.WARNING)` が `logging.WARNING` に
  フォールバックするだけで、呼び出し元はエラーに気づかない。
  ロガー設定ミスはデバッグが困難な症状（ログが出ない・出すぎる）をもたらす。
- **GAP-2**: **`datetime.utcnow()` は Python 3.12 で非推奨**: `JSONFormatter.format` が
  `datetime.utcnow().isoformat()` を使用。Python 3.12+ で `DeprecationWarning` を発生させる。
  `datetime.now(timezone.utc).isoformat()` に置き換えが必要。
- **GAP-3**: **`configure_logging` のデフォルト `json_format=True` が plain-text フォーマッターを
  使う場合に `%(correlation_id)s` プレースホルダーを含む**: plain-text フォーマッターに
  `CorrelationIdFilter` が付いていないと `LogRecord` に `correlation_id` 属性がなく
  `KeyError` になる可能性がある（実際は `addFilter` しているが、テストで確認が必要）。

## 2. 要件

| ID | 要件 | 状況 | 実装 |
|---|---|---|---|
| REQ-LC-01 | 無効レベル文字列 → `ValueError` | ✅ 実装済 | `_validate_level` |
| REQ-LC-02 | `utcnow()` → `now(timezone.utc)` | ✅ 実装済 | `JSONFormatter.format` |
| REQ-LC-03 | `JSONFormatter` の ISO-8601 UTC タイムスタンプ (Zサフィックス) | ✅ 実装済 | `+00:00` または `Z` 形式 |
| REQ-LC-04 | `get_logger` / `set_correlation_id` の既存動作は不変 | — | 変更なし |

## 3. 仕様詳細

### `_validate_level(level: str) -> int`（内部ヘルパー）
許可値: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`（大文字小文字不問）。
それ以外: `ValueError(f"Invalid log level: {level!r}. Must be one of ...")` を送出。

### `configure_logging(...)`（REQ-LC-01）
先頭で `_validate_level(level)` を呼び、その戻り値（数値）を使用。

### `JSONFormatter.format`（REQ-LC-02/03）
```python
from datetime import timezone
"timestamp": datetime.now(timezone.utc).isoformat()
```

## 4. 受け入れ基準（テスト）
`tests/test_logging_config.py`（stdlib unittest, 本環境で実行可能）。
