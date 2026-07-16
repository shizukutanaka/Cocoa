# 仕様書: バッチパラメータバリデーター

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/parameters_batch_validator.py`
**目的**: バッチ検証の要件を明文化し、セキュリティ欠陥と堅牢性の不足を修正する。

## 1. 現状とギャップ

`parameters_batch_validator.py` はディレクトリ内の複数プリセット JSON を一括型検証する。
コード実査で次の問題を確認:

- **GAP-1**: **`eval(v)` によるコードインジェクション脆弱性**: `main()` が `type_map` の値を
  `eval()` で Python 型に変換 → 外部 JSON ファイルから任意コードを実行可能。
  ホワイトリスト変換に置き換えが必須。
- **GAP-2**: **`batch_validate_presets` が例外をキャッチしない**: `json.load` や
  `open` が失敗した場合、イテレーション全体がクラッシュする。
- **GAP-3**: **辞書入力 API が無い**: ファイルシステムなしで単一プリセットを検証する
  `validate_parameter_types_dict` 関数が無い。テスト・埋め込みユース向け。
- **GAP-4**: **`preset_dir` の存在チェックが無い**: 存在しないディレクトリを渡すと
  `FileNotFoundError`（`os.listdir`）がそのまま伝播する。
- **GAP-5**: **集計サマリーが無い**: `batch_validate_presets` はエラーのある
  ファイルしか返さない。total/pass/fail の内訳が必要。

## 2. 型名ホワイトリスト

`main()` で JSON から型マップを受け取る際、許可する型名を次のとおり固定:

| 文字列 | Python 型 |
|---|---|
| `"bool"` | `bool` |
| `"int"` | `int` |
| `"float"` | `float` |
| `"str"` | `str` |
| `"list"` | `list` |
| `"dict"` | `dict` |

その他の文字列は `ValueError` を発生させる（`eval` への委譲は禁止）。

## 3. 要件

| ID | 要件 | 状況 | 実装 |
|---|---|---|---|
| REQ-BV-01 | 型チェック（既存） | ✅ | `validate_parameter_types` |
| REQ-BV-02 | eval 排除・ホワイトリスト型変換 | ✅ 実装済 | `_parse_type_map` |
| REQ-BV-03 | バッチ検証の堅牢性（JSON エラー・IO エラーをスキップ） | ✅ 実装済 | `batch_validate_presets` |
| REQ-BV-04 | 辞書入力 API | ✅ 実装済 | `validate_parameter_types` (変更なし, 既存シグネチャ維持) |
| REQ-BV-05 | `preset_dir` 存在チェック | ✅ 実装済 | `batch_validate_presets` |
| REQ-BV-06 | 集計サマリー付き戻り値 | ✅ 実装済 | `batch_validate_presets` → `{"errors": {...}, "summary": {...}}` |

## 4. 仕様詳細

### `_parse_type_map(type_map: dict) -> dict`（内部ヘルパー）
- `type_map` の各値をホワイトリスト（上記 6 型）で変換。
- 不明な型名は `ValueError("Unsupported type: <name>")` を送出。

### `validate_parameter_types(preset, param_types) -> dict[str, str]`
- シグネチャ・動作は既存のまま変更なし。
- `preset` に存在しないキーはスルー（型名不一致のみエラー対象）。

### `batch_validate_presets(preset_dir, param_types) -> dict`
- 戻り値: `{"errors": {filename: {field: msg, ...}, ...}, "summary": {"total": N, "passed": N, "failed": N}}`
- `preset_dir` が存在しない・ディレクトリでない場合は `{"errors": {}, "summary": {"total": 0, "passed": 0, "failed": 0, "error": "<message>"}}` を返す（例外伝播しない）。
- 各 `.json` ファイルの `json.load` や `open` が失敗した場合はそのファイルをスキップ（ログ警告）。

### `main()`
- `param_types_json` ファイルを `_parse_type_map` で安全に変換（`eval` 禁止）。

## 5. 受け入れ基準（テスト）

`tests/test_batch_validator.py`（stdlib unittest + `tempfile`, 本環境で実行可能）:
- 型不一致・型一致・存在しないキーのスルー（`validate_parameter_types`）
- ホワイトリスト変換の正常・異常（`_parse_type_map`）
- バッチ：混在ディレクトリ（正常/エラーあり/JSON壊れ）でのサマリー
- バッチ：存在しないディレクトリでのエラー耐性

## 6. 後方互換
`validate_parameter_types` と `batch_validate_presets` の既存呼び出しは影響なし。
`batch_validate_presets` の戻り値形式が変わるため、呼び出し元の `main()` を更新済み。
