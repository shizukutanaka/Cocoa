# 仕様書: テンプレートライブラリ サブシステム

**版**: 1.0 / **作成日**: 2026-06-05 / **対象**: `template_library` および抽出モジュール `template_filters`
**目的**: テンプレート管理の要件を明文化し、不足（スキーマ検証・ID安全性）を特定して実装する。

## 1. 背景と問題
`template_library.py` は `integrated_security`（cryptography ネイティブ依存）に結合しており
本環境では import/テスト不可。さらにコード実査で次の不足を確認:
- **(GAP-1 セキュリティ) `template_id` のパストラバーサル**: `save_*`/`delete_template` が
  `dir / f"{template_id}.json"` を組み立てる。`template_id` に `../` 等が含まれると
  テンプレートディレクトリ外へ書込/削除し得る。
- **(GAP-2) テンプレートのスキーマ検証が無い**: `load_templates` は `AvatarTemplate(**data)` を
  直接構築し、不正データは例外→ログのみで黙って無視。形式検証が無い。
- **(GAP-3) フィルタ/検索ロジックが暗号依存クラスに内包**され、単体テスト不能。

## 2. 方針
純粋・依存なしの `main/template_filters.py` を新設し、検証/ID安全化/フィルタ/検索を提供。
`template_library` はこれを利用（特に GAP-1 のID安全化を save/delete に配線）。

## 3. 要件
| ID | 要件 | 実装 |
|---|---|---|
| REQ-TL-01 | `template_id` の安全化（パス区切り/`..`/制御文字を拒否） | `template_filters.sanitize_template_id` |
| REQ-TL-02 | アバターテンプレートの形式検証（必須: template_id,name,description,category,style） | `validate_avatar_template` |
| REQ-TL-03 | 動画テンプレートの形式検証（必須: …,script_template） | `validate_video_template` |
| REQ-TL-04 | カテゴリ/タグ/プレミアムでのフィルタ（純関数, dict対応） | `filter_templates` |
| REQ-TL-05 | 名前/説明/タグ横断の検索（純関数） | `search_templates` |
| REQ-TL-06 | save/delete でのID安全化配線（GAP-1 修正） | `template_library`（`sanitize_template_id` 利用） |

## 4. 仕様詳細
- **REQ-TL-01** `sanitize_template_id(tid) -> str`
  - 非空 str 必須。`/` `\` NUL、`.`/`..`、部分文字列 `..` を含むものは `ValueError`。
  - 許容文字は `[A-Za-z0-9_.-]` のみ。正常時は trim 済みIDを返す。
- **REQ-TL-02/03** `validate_*_template(data) -> {valid, errors}`
  - dict 必須。必須キーは非空 str。`tags` があれば str のリスト。`template_id` は REQ-TL-01 を満たす。
- **REQ-TL-04** `filter_templates(items, category=None, tags=None, premium_only=False)`
  - items は dict のリスト。一致するもののみ返す（tags は OR 一致）。
- **REQ-TL-05** `search_templates(items, query)`
  - name/description/tags を小文字で横断検索し、`usage_count` 降順で返す。

## 5. 受け入れ基準（テスト）
`tests/test_template_filters.py`（stdlib unittest, 本環境で実行可能, 15件全パス）。

## 実装状況
全要件 REQ-TL-01〜06 実装済。GAP-1（パストラバーサル）は `template_library` の
save/delete に `sanitize_template_id` を配線して修正。GAP-2（スキーマ検証無し）は
`load_templates` で `validate_*_template` を適用し不正テンプレートをスキップ。

## 6. 参照
[`CATEGORY_RESEARCH.md`](CATEGORY_RESEARCH.md) カテゴリ4 / [`SPEC_PRESET_PARAMETERS.md`](SPEC_PRESET_PARAMETERS.md)
