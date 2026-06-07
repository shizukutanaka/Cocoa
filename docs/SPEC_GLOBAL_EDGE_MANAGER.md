# 仕様書: GlobalEdgeManager

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/global_edge_manager.py`
**目的**: `datetime.now()` ナイーブ化（11 箇所）の修正。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-GEM-01 | `datetime.now()` を 11 箇所で使用（EdgeNode 生成、ヘルスチェック、キャッシュ管理等） | Python 3.12+ DeprecationWarning; UTC 一貫性の欠如 |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-GEM-01 | 全 `datetime.now()` → `datetime.now(timezone.utc)` | `from datetime import datetime, timedelta, timezone` |

## 3. 受け入れ基準（テスト）

`tests/test_global_edge_manager.py`（stdlib unittest, numpy なしで動作）:
- `GlobalEdgeManager()` が作成できる（tempdir 使用）
- `edge_nodes / content_cache / traffic_routes` が初期化される
- `get_edge_stats()` が dict を返す
- `get_edge_node()` は存在しないノードで `None` を返す
- `register_edge_node()` でノードを登録・取得できる
- 登録ノードの `last_health_check` が UTC-aware である
