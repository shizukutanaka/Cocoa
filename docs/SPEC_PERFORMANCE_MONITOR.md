# 仕様書: PerformanceMonitor

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/performance_monitor.py`
**目的**: `datetime.utcnow()` 廃止対応（9 箇所 + datetime.now() ナイーブ化）。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-PM-01 | `datetime.utcnow()` を 9 箇所で使用 | Python 3.12+ で DeprecationWarning |
| GAP-PM-02 | `_format_datetime()` 内の `datetime.now()` がナイーブ | タイムゾーン不整合の可能性 |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-PM-01 | 全 `datetime.utcnow()` → `datetime.now(timezone.utc)` | `from datetime import datetime, timezone` |
| REQ-PM-02 | `_format_datetime()` の `datetime.now()` → `datetime.now(timezone.utc)` | 同上 |

## 3. 受け入れ基準（テスト）

`tests/test_performance_monitor.py`（stdlib unittest, psutil なしで動作）:
- `PerformanceMonitor()` が作成できる
- `get_performance_report()` の timestamp が UTC 形式（+00:00）
- `validate_config()` が dict を返す
- `get_custom_metrics()` が dict を返す
- カスタムメトリクスを登録して取得できる
