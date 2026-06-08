# 仕様書: CocoaHealthChecker (scripts/health_checker.py)

**版**: 1.0 / **作成日**: 2026-06-08 / **対象**: `scripts/health_checker.py`
**目的**: 言語ファイル検出の長さ判定バグと bare-except を修正。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-HC-01 | `_check_language_files()` が `len(f.name) == 6` で `main/` 内の言語ファイルを判定 | `"ja.json"` 等の2文字コードは7文字なので**一致せず**、検出すべき main 配下の言語ファイル（コメントは "xx.json"）を取りこぼす。代わりに1文字コード `"x.json"`（6文字）のみ一致する誤判定 |
| GAP-HC-02 | `_check_duplicate_files()` / `_check_security_issues()` に bare `except:` | `KeyboardInterrupt`/`SystemExit` も握りつぶす。ruff E722 |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-HC-01 | 2文字言語コードの `xx.json` を正しく判定する | `len(f.stem) == 2`（拡張子を除いたステムで判定） |
| REQ-HC-02 | bare `except:` を `except Exception:` に置換 | 2 箇所 |

## 3. 受け入れ基準（テスト）

`tests/test_health_checker.py`（stdlib unittest, tempfile のみ使用）:
- `CocoaHealthChecker(project_root)` が作成できる
- `_check_project_structure()` が欠落ディレクトリを issue に記録する
- 全必須ディレクトリ/ファイル存在時は passed_checks に記録する
- `_check_language_files()` が `main/ja.json` を検出して warning を出す（REQ-HC-01）
- `_check_language_files()` が `main/x.json`（1文字）を 2文字コードとして誤検出しない
- `_check_documentation()` が README 欠如を issue にする
- `_check_dependencies()` が requirements.txt 欠如を warning にする
- ソースに bare `except:` が存在しない（REQ-HC-02、ruff E722 = 0）
