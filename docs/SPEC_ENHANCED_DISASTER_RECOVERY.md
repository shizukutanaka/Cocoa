# 仕様書: enhanced_disaster_recovery

**版**: 1.0 / **作成日**: 2026-06-08 / **対象**: `main/enhanced_disaster_recovery.py`
**目的**: `datetime.now()` ナイーブ化（13 箇所）の修正。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-EDR-01 | `datetime.now()` を 13 箇所で使用（backup 名生成、duration 計算、timestamp 保存、days フィルタ等） | Python 3.12+ DeprecationWarning; `list_backups(days=N)` でナイーブ/aware 混在 TypeError |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-EDR-01 | 全 `datetime.now()` → `datetime.now(timezone.utc)` | `from datetime import datetime, timedelta, timezone` |

## 3. 受け入れ基準（テスト）

`tests/test_enhanced_disaster_recovery.py`（stdlib unittest, tempfile のみ使用）:
- `Enhanced321BackupManager()` が作成できる
- `list_backups()` が空ディレクトリで `[]` を返す
- `BackupConfig` / `RPOConfig` / `RTOConfig` dataclass が構築できる
- `BackupLocation` / `StorageType` / `RecoveryStrategy` Enum が使える
