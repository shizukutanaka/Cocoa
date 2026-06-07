# 仕様書: validate_and_repair_presets

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/validate_and_repair_presets.py`
**目的**: datetime ナイーブ化・`metrics_history` 破壊バグの修正。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-VRP-01 | `backup_file()` の `datetime.now()` がナイーブ | Python 3.12+ DeprecationWarning; UTC 一貫性の欠如 |
| GAP-VRP-02 | `end_operation()` が `PerformanceMonitor.metrics_history` に平リスト `[]` を代入 | 境界なし・型不整合・スレッドセーフ違反 |
| GAP-VRP-03 | `get_performance_report()` がロック未取得で `_build_history_summary_locked()` を呼び出す | 潜在的なレースコンディション |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-VRP-01 | `backup_file()` の timestamp は UTC 取得 | `datetime.now(timezone.utc).strftime(...)` |
| REQ-VRP-02 | `PresetPerformanceMonitor` は operation 履歴を自身の `_op_history: Dict[str, deque]` に保持する | `__init__` に `self._op_history = {}; self._history_maxlen = 100` |
| REQ-VRP-03 | `end_operation()` は `metrics_history` を書き換えず `_op_history` に追記する | bounded `deque(maxlen=_history_maxlen)` |
| REQ-VRP-04 | `get_performance_report()` は `_op_history` から集計を行い `_build_history_summary_locked()` を呼ばない | self-contained 集計 |

## 3. 受け入れ基準（テスト）

`tests/test_validate_and_repair_presets.py`（stdlib unittest, tempfile のみ使用）:
- `repair_preset()` が必須キーを補完する
- `repair_preset()` が不正型パラメータを修正する
- `backup_file()` が実際にファイルを作成する
- `validate_and_repair_dir()` が空ディレクトリで空リストを返す
- `validate_and_repair_dir()` が壊れた JSON をエラーとして記録する
- `validate_and_repair_dir()` が修復された場合 `"repaired": True` を返す
- `PresetPerformanceMonitor` の作成が成功する
- `start_operation` / `end_operation` で `operation_stats` に記録される
- `get_performance_report()` が必須キーを返す
- `PerformanceMonitor.metrics_history` が操作後に変更されない
