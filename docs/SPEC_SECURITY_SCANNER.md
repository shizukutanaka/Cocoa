# 仕様書: SecurityScanner (security_scanner.py)

**版**: 1.0 / **作成日**: 2026-06-08 / **対象**: `scripts/security_scanner.py`
**目的**: ナイーブ datetime と、依存関係脆弱性検出のデッドロジックを修正。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-SS-01 | `scan_all()` の `datetime.now().isoformat()` がナイーブ | Python 3.12+ DeprecationWarning; レポート timestamp の TZ 不整合 |
| GAP-SS-02 | `check_dependencies()` がピン留めバージョンを抽出するが `min_version` と**比較しない** | `vulnerable_packages` が常に空 → status が常に `pass`。脆弱な依存を検出できない |

`vulnerable_patterns` は `{'Flask': '<2.3.0', ...}` の形式で、「指定バージョン**未満**なら脆弱」を表す。
現行コードは `if '==' in line` でピン留めを検知し recommendation を足すだけで、実際のバージョン比較を行わない。

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-SS-01 | `scan_all()` timestamp を UTC-aware にする | `datetime.now(timezone.utc).isoformat()` |
| REQ-SS-02 | バージョン比較ヘルパー `_parse_version(s) -> tuple[int,...]` を追加 | `"2.3.0" -> (2,3,0)`、非数値要素は無視 |
| REQ-SS-03 | `_is_version_vulnerable(installed, constraint) -> bool` を追加 | `constraint="<2.3.0"` で installed が未満なら True |
| REQ-SS-04 | `check_dependencies()` はピン留め（`==`）バージョンが脆弱な場合 `vulnerable_packages` に追加し status を `fail` にする | 比較結果に基づく |

## 3. 受け入れ基準（テスト）

`tests/test_security_scanner.py`（stdlib unittest, tempfile のみ使用）:
- `_parse_version("2.3.0")` → `(2, 3, 0)`
- `_parse_version("1.4")` → `(1, 4)`
- `_parse_version` が非数値サフィックス（`"2.3.0rc1"` 等）を許容する
- `_is_version_vulnerable("2.2.0", "<2.3.0")` → True
- `_is_version_vulnerable("2.3.0", "<2.3.0")` → False
- `_is_version_vulnerable("2.4.0", "<2.3.0")` → False
- `scan_all()` の timestamp が UTC 形式（`+00:00`）
- requirements.txt 欠如時に `check_dependencies()` が `warning` を返す
- 脆弱なピン留めパッケージが `vulnerable_packages` に検出され status が `fail`
- 安全なピン留めパッケージは検出されず status が `pass`
- `SecurityScanner(base_dir=...)` が作成できる
