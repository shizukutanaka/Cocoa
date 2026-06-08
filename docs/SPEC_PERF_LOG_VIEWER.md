# 仕様書: perf_log_viewer (scripts/perf_log_viewer.py)

**版**: 1.0 / **作成日**: 2026-06-08 / **対象**: `scripts/perf_log_viewer.py`
**目的**: PerformanceMonitor の JSON ログ閲覧ツールの純粋関数を仕様化・回帰固定。

## 1. 現状とギャップ

コードは正常。ギャップなし。テストカバレッジが欠如しており、パース/整形ロジックが
無保護のため回帰検知できない。

## 2. 関数仕様（回帰固定対象）

| 関数 | 仕様 |
|---|---|
| `iter_log_entries(path)` | 各行を JSON としてパースし dict を yield。空行・不正 JSON 行はスキップ。存在しないパスは `FileNotFoundError` |
| `collect_snapshots(path)` | `message == "performance_snapshot"` のエントリのみ収集。`{timestamp, stats}` のリストを返す |
| `extract_metric(stats, "a.b.c")` | ドット区切りでネスト dict を辿り値を返す。経路欠落時は `None` |
| `format_value(v)` | `None`→`"-"`、数値で `abs>=100`→桁区切り整数、`<100`→小数2桁、その他→`str(v)` |

## 3. 受け入れ基準（テスト）

`tests/test_perf_log_viewer.py`（stdlib unittest, tempfile のみ使用）:
- `extract_metric({"a": {"b": 5}}, "a.b")` → `5`
- `extract_metric(..., "a.x")` → `None`（欠落経路）
- `extract_metric` がスカラを途中で辿ろうとした場合 `None`
- `format_value(None)` → `"-"`
- `format_value(150.0)` → `"150"`（桁区切り、整数表示）
- `format_value(12.345)` → `"12.35"`（小数2桁）
- `format_value(1234.5)` → `"1,234"`（桁区切り）
- `format_value("text")` → `"text"`
- `iter_log_entries()` が不正 JSON 行と空行をスキップする
- `iter_log_entries()` が存在しないパスで `FileNotFoundError`
- `collect_snapshots()` が `performance_snapshot` メッセージのみ収集する
- `collect_snapshots()` が非該当メッセージを無視する
- `parse_args()` が既定値を返す
