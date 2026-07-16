# 仕様書: 言語ファイル管理スクリプト (consolidate_languages.py / move_languages.py)

**版**: 1.0 / **作成日**: 2026-06-08
**対象**: `scripts/consolidate_languages.py`, `scripts/move_languages.py`
**目的**: ハードコードされた `project_root` を注入可能にし、結果を戻り値で観測可能にする（テスト容易性＋ライブラリ再利用性）。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-LANG-01 | `consolidate_language_files()` が `project_root` を `Path(__file__).parent.parent` で固定 | 任意ディレクトリに対して実行・テスト不可 |
| GAP-LANG-02 | 同関数が結果を `print` のみで返さない | 統合/スキップ件数をプログラムから取得できない |
| GAP-LANG-03 | `move_remaining_languages()` も同様に `project_root` 固定・戻り値なし | テスト・再利用不可 |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-LANG-01 | `consolidate_language_files(project_root=None, lang_codes=None) -> dict` | 既定は実プロジェクトルート。`{"consolidated": int, "skipped": int}` を返す |
| REQ-LANG-02 | locales に未存在ならファイルを移動、存在すれば JSON マージ（locales 優先）して main を削除 | 既存挙動を保持 |
| REQ-LANG-03 | `move_remaining_languages(project_root=None, langs=None) -> dict` | 既定は実プロジェクトルート。`{"moved": int}` を返す |
| REQ-LANG-04 | CLI 実行（`__main__`）は従来通り引数なしで動作 | 後方互換 |

## 3. 受け入れ基準（テスト）

`tests/test_language_scripts.py`（stdlib unittest, tempfile のみ使用）:

consolidate:
- locales 未存在の言語ファイルが locales へ移動され main から消える
- locales 既存の場合 JSON がマージされ、競合キーは locales 優先
- main に該当ファイルが無い言語はスキップ件数に計上
- 戻り値が `{"consolidated", "skipped"}` を含む
- 不正 JSON（マージ対象）でスキップ計上され、例外を送出しない

move:
- main の言語ファイルが locales へコピーされ main から削除される
- 戻り値が `{"moved": n}` を含む
- 存在しないファイルは moved に計上されない
- 既存 locales ファイルを上書きする
