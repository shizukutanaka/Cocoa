# 仕様書: 国際化 (i18n) モジュール

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/i18n.py`
**目的**: ロケール正規化・フォールバックチェーン・`t()` バグを明文化し実装する。

## 1. 現状とギャップ

`i18n.py` の `I18N` クラスは `SATIN_LANG` 環境変数または `locale.getdefaultlocale()`
でシステム言語を検出し、JSON 翻訳ファイルを読み込む。コード実査で次の不足を確認:

- **GAP-1**: **ロケールコード正規化が不完全**: `detect_language()` は
  `loc.lower().split('_')[0]` で言語部のみ取得。`zh_TW` → `zh` になるため
  繁体字中国語ユーザーが簡体字 `zh` のフォントと翻訳を受け取る。
  POSIX スタイル `language_REGION` を IETF BCP-47 スタイル `language-region`
  (小文字) に変換すべき。
- **GAP-2**: **フォールバックチェーンが無い**: `load_translation` は
  `zh-tw.json` が無い場合に直接 `en.json` に飛ぶ。
  `zh-tw` → `zh` → `en` のように言語ファミリーへフォールバックすべき。
- **GAP-3**: **`t()` の default 引数バグ**: `default or key` は
  `default=""` のとき falsy なので `key` を返してしまう。
  `key if default is None else default` が正しい。

## 2. 要件

| ID | 要件 | 状況 | 実装 |
|---|---|---|---|
| REQ-I18N-01 | 言語検出（既存） | ✅ | `detect_language` |
| REQ-I18N-02 | 翻訳ファイル読み込み・キャッシュ（既存） | ✅ | `load_translation` |
| REQ-I18N-03 | POSIX→BCP-47 ロケール正規化 | ✅ 実装済 | `_normalize_lang` |
| REQ-I18N-04 | フォールバックチェーン (`lang-region`→`lang`→`en`) | ✅ 実装済 | `load_translation` |
| REQ-I18N-05 | `t()` の `default=""` バグ修正 | ✅ 実装済 | `t` |
| REQ-I18N-06 | フォントマップのフォールバック（`zh-tw`→`zh` キー） | ✅ 実装済 | `I18N.__init__` |

## 3. 仕様詳細

### `_normalize_lang(lang: str) -> str`（モジュールレベルヘルパー）
- `lang` を小文字にし、`_` を `-` に置換（例: `zh_TW` → `zh-tw`）。
- 空文字列はそのまま返す。

### `load_translation(lang: str) -> dict`
フォールバックチェーン（最初に見つかったものを返す）:
1. `{lang}.json` (例: `zh-tw.json`)
2. `{lang.split('-')[0]}.json` (例: `zh.json`)
3. `en.json`
4. `{}` (いずれも読み込めない場合)

キャッシュは正規化済み `lang` をキーとする。

### `t(key: str, default=None) -> str`
- `default is None` の場合にのみ `key` にフォールバック。
- `default=""` は `""` を返す（空文字列を有効な翻訳として扱う）。

### `get_font(size=12, weight="normal")`
- `FONT_MAP.get(self.lang)` が `None` のとき、`self.lang.split('-')[0]` で
  再検索（例: `zh-tw` に無くても `zh` のフォントを返す）。
- それでも無い場合は `'Arial'` を返す（既存の動作を維持）。

## 4. 受け入れ基準（テスト）

`tests/test_i18n.py`（stdlib unittest, tmpdir + モック, 本環境で実行可能）:
- `_normalize_lang`: POSIX/BCP-47/小文字入力の変換
- `load_translation`: フォールバックチェーン（zh-tw → zh → en）
- `t()`: 翻訳あり・翻訳なし・default=None・default=""
- `get_font()`: zh-tw のフォールバックフォント検索

## 5. 後方互換
- `I18N(lang=None)` のシグネチャは不変。
- `t(key, default=None)` のシグネチャは不変（`default or key` → バグ修正のみ）。
- キャッシュは既存のクラス変数 `_translation_cache` を継続使用。
