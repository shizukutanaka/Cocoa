# 仕様書: LanguageFileGenerator (scripts/generate_languages.py)

**版**: 1.0 / **作成日**: 2026-06-08 / **対象**: `scripts/generate_languages.py`
**目的**: ネスト locales_dir での mkdir 失敗を修正し、純粋な翻訳ロジックを回帰固定。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-GL-01 | `__init__` が `locales_dir.mkdir(exist_ok=True)`（`parents` 無し） | ネストした locales パス（親不在）で `FileNotFoundError` |
| GAP-GL-02 | 再帰翻訳・ディスパッチ・ファイル生成にテストが無い | 構造保持/フォールバック挙動が無保護 |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-GL-01 | locales ディレクトリは親も作成する | `mkdir(parents=True, exist_ok=True)` |
| REQ-GL-02 | `_translate_content` は dict/list/非文字列の構造を保持し文字列のみ翻訳する | 既存の再帰実装を固定 |
| REQ-GL-03 | `_simple_translate` は未知の言語コードで原文（英語）を返す | フォールバック挙動を固定 |
| REQ-GL-04 | `create_language_file` は既存ファイルをスキップし True を返す | 既存挙動を固定 |

## 3. 受け入れ基準（テスト）

`tests/test_generate_languages.py`（stdlib unittest, tempfile のみ使用）:
- `LanguageFileGenerator(locales_dir=...)` がネストパスでも作成できる（REQ-GL-01）
- `_simple_translate("Home", "ja", ...)` が日本語訳「ホーム」を返す
- `_simple_translate("Home", "xx", ...)`（未知コード）が原文 "Home" を返す（REQ-GL-03）
- `_simple_translate("UnknownPhrase", "ja", ...)` が未知語をそのまま返す
- `_translate_content` がネスト dict/list 構造を保持する（REQ-GL-02）
- `_translate_content` が非文字列値（int/bool/None）をそのまま保持する
- `create_language_file` が新規ファイルを作成し True を返す
- `create_language_file` が既存ファイルをスキップして True を返し内容を変更しない（REQ-GL-04）
- `load_english_template` が en.json 不在で `FileNotFoundError`
- `load_english_template` が en.json を読み込める
