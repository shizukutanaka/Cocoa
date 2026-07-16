# 仕様書: grafana_integration

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/grafana_integration.py`
**目的**: `datetime.now()` ナイーブ化（4 箇所）の修正。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-GI-01 | `datetime.now().isoformat()` を 4 箇所で使用 | Python 3.12+ DeprecationWarning; UTC 一貫性の欠如 |
| GAP-GI-02 | `EnhancedPerformanceMonitor.__init__` の `config.get('grafana_api_key')` が `config=None` 時に `AttributeError` | デフォルト引数で構築不可 |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-GI-01 | 全 `datetime.now().isoformat()` → `datetime.now(timezone.utc).isoformat()` | `from datetime import datetime, timezone` |

## 3. 受け入れ基準（テスト）

`tests/test_grafana_integration.py`（stdlib unittest, psutil なしで動作）:
- `EnhancedPerformanceMonitor()` が作成できる
- `get_performance_report()` が空履歴時でもクラッシュしない
- `GrafanaMetricsCollector()` が作成できる
- `GrafanaDashboardManager()` が作成できる
- `get_enhanced_performance_monitor()` がシングルトンを返す
- timestamp フィールドが UTC 形式（`+00:00`）
