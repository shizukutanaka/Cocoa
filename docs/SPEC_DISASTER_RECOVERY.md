# 仕様書: DisasterRecoveryManager

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/disaster_recovery.py`
**目的**: 初期化バグ修正と datetime.utcnow() 廃止対応。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-DR-01 | `self.backup_metadata` が `__init__` で初期化されていない | `create_backup()` 等すべてのメソッドが `AttributeError` でクラッシュ |
| GAP-DR-02 | `self.metadata_file` が `__init__` で初期化されていない | `_save_metadata()` / `_load_metadata()` が `AttributeError` でクラッシュ |
| GAP-DR-03 | `_load_metadata()` が `__init__` から呼ばれていない | 既存のバックアップメタデータが読み込まれない |
| GAP-DR-04 | `datetime.utcnow()` を 7 箇所で使用 | Python 3.12+ で DeprecationWarning |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-DR-01 | `__init__` で `backup_metadata` と `metadata_file` を初期化し `_load_metadata()` を呼ぶ | 3 行を `__init__` 末尾に追加 |
| REQ-DR-02 | `datetime.utcnow()` → `datetime.now(timezone.utc)` | `from datetime import datetime, timedelta, timezone` |

## 3. 仕様詳細

### `__init__` 修正 (REQ-DR-01)

`self.retention_policy = { ... }` の後に追加:

```python
self.metadata_file = self.backup_dir / 'backup_metadata.json'
self.backup_metadata: List[BackupMetadata] = []
self._load_metadata()
```

### `datetime.utcnow()` 置き換え (REQ-DR-02)

```python
from datetime import datetime, timedelta, timezone
# すべての datetime.utcnow() を datetime.now(timezone.utc) に置き換え
```

## 4. 受け入れ基準（テスト）

`tests/test_disaster_recovery.py`（stdlib unittest, tmpdir を使用）:
- `DisasterRecoveryManager()` がクラッシュしない（REQ-DR-01 regression）
- `backup_metadata` が空リストで初期化される
- `get_recovery_status()` の timestamp が UTC 形式
- `list_backups()` が空リストを返す（バックアップなし）
- `_get_earliest_retention_date()` が timezone-aware な datetime を返す
