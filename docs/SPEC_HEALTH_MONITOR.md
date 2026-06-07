# 仕様書: HealthMonitor

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/health_monitor.py`
**目的**: `datetime.utcnow()` 廃止対応と `register_check()` の型安全性向上。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-HM-01 | `datetime.utcnow()` が4箇所で使用されている | Python 3.12+ で DeprecationWarning; 3.14 で削除予定 |
| GAP-HM-02 | `register_check(name, check_func)` が `check_func` の callable チェックをしていない | 非 callable を登録すると `run_all_checks()` が TypeError でクラッシュ |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-HM-01 | `datetime.utcnow()` → `datetime.now(timezone.utc)` | `from datetime import datetime, timezone` に変更 |
| REQ-HM-02 | `register_check()` は callable でない `check_func` に `TypeError` を送出 | `if not callable(check_func): raise TypeError(...)` |

## 3. 仕様詳細

### `datetime.utcnow()` 置き換え (REQ-HM-01)

`from datetime import datetime` を `from datetime import datetime, timezone` に変更し:

- `HealthCheckResult.timestamp` の default_factory:
  `datetime.now(timezone.utc).isoformat()`
- `run_all_checks()` の timestamp:
  `datetime.now(timezone.utc).isoformat()`
- `get_readiness()` の timestamp:
  `datetime.now(timezone.utc).isoformat()`
- `get_liveness()` の timestamp (2箇所):
  `datetime.now(timezone.utc).isoformat()`

### `register_check()` 型チェック (REQ-HM-02)

```python
def register_check(self, name: str, check_func: Callable):
    if not callable(check_func):
        raise TypeError(
            f"check_func must be callable, got {type(check_func).__name__!r}"
        )
    self.checks[name] = check_func
    ...
```

## 4. 受け入れ基準（テスト）

`tests/test_health_monitor.py`（stdlib unittest, psutil なしで動作）:
- `HealthCheckResult.timestamp` が UTC (+00:00) 形式
- `run_all_checks()` の timestamp が UTC 形式
- `register_check()` に非 callable を渡すと `TypeError`
- カスタムチェックを登録して実行できる
- `get_liveness()` が `alive: True` と `uptime_seconds` を返す
- `get_readiness()` が `ready` キーを持つ辞書を返す
