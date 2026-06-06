# 仕様書: プリセット & パラメータ管理サブシステム

**版**: 1.0 / **作成日**: 2026-06-05 / **対象**: Cocoa の preset/parameter 系モジュール群
**目的**: 本サブシステムの要件を明文化し、実装の充足/不足(ギャップ)を特定して不足を実装する。

## 1. スコープと参照
- 対象モジュール: `preset_manager`, `preset_diff_core`, `validate_and_repair_presets`,
  `preset_change_history` / `preset_history_*`, `template_library`, `config_validator`,
  `parameter_optimizer`, `avatar_parameters`。
- 外部参照: VRChat Avatar 3.0 Expression Parameters / Performance Ranking
  （[`CATEGORY_RESEARCH.md`] カテゴリ4, [`IMPROVEMENT_BACKLOG.md`]）。

## 2. データモデル
- **Preset**: JSON。必須キー `name: str`, `parameters: list`。任意の付加メタを許容。
- **Expression Parameter**（VRChat 同期パラメータ）: `{ "name": str, "type": "Bool"|"Int"|"Float"|"Trigger", "synced": bool, "default": any }`。
  - 同期コスト(ビット): **Bool=1, Trigger=1, Int=8, Float=8**。`synced=False` は予算に計上しない。
  - 同期予算: **256 ビット**（VRChat のユーザ定義同期パラメータ上限）。

## 3. 要件と充足状況（ギャップ分析）

| ID | 要件 | 状況 | 実装/担当 |
|---|---|---|---|
| REQ-PM-01 | プリセットの JSON ロード/セーブ | ✅ | `preset_diff_core.load_preset`, `preset_manager` |
| REQ-PM-02 | プリセット自動修復（必須キー補完・型修正） | ✅ | `validate_and_repair_presets.repair_preset` |
| REQ-PM-03 | プリセット差分（テキスト/HTML） | ✅ | `preset_diff_core.diff_presets/generate_html_diff` |
| REQ-PM-04 | 変更履歴・ロールバック | ✅ | `preset_change_history`, `preset_history_diff_and_rollback` |
| REQ-PM-05 | テンプレート管理 | ✅ | `template_library` |
| REQ-PM-06 | 設定の検証（必須/型/範囲/列挙） | ✅ | `config_validator.validate_from_dict` |
| REQ-PM-07 | プリセットの形式検証（スキーマ） | 🟡 部分 | 修復はあるが形式スキーマ検証は無い |
| REQ-PM-08 | パラメータ値の最適化 | 🟡 部分 | `parameter_optimizer`（numpy 値最適化のみ） |
| **REQ-PM-09** | **VRChat 同期パラメータのコスト計算（型→ビット）** | ✅ **実装済** | `vrchat_parameter_budget.parameter_cost` |
| **REQ-PM-10** | **256bit 同期予算の判定・超過検出** | ✅ **実装済** | `vrchat_parameter_budget.analyze_budget` |
| **REQ-PM-11** | **予算最適化提案（型ダウングレード/未同期化）** | ✅ **実装済** | `vrchat_parameter_budget.suggest_optimizations` |

## 4. 不足の詳細仕様（本変更で実装する REQ-PM-09/10/11）

新規モジュール `main/vrchat_parameter_budget.py`:

- **REQ-PM-09** `parameter_cost(param) -> int`
  - 入力: パラメータ dict（`type`, `synced`）。`synced=False` → 0。
  - 型→ビット: Bool/Trigger=1, Int/Float=8。未知の型は `ValueError`。大文字小文字非依存。
- **REQ-PM-10** `analyze_budget(parameters) -> dict`
  - 返り値: `{ used_bits, remaining_bits, budget_bits(=256), over_budget: bool,
    synced_count, breakdown: {Bool:n,...}, per_type_bits: {...} }`。
- **REQ-PM-11** `suggest_optimizations(parameters) -> list[str]`
  - 予算超過時に削減案を提示:
    1. Float で `default` が 0/1 等の二値とみなせるものは **Bool 化**（8→1bit, 7bit削減）。
    2. 同期不要候補（命名に `local`/`_local` を含む等）は **未同期化**（synced=False）。
    3. なお超過なら、超過ビット数と「ビットパッキング(OSC)で複数 float を集約」する旨を案内。

## 5. 受け入れ基準（テスト）
`tests/test_vrchat_budget.py`（stdlib unittest, 本環境で実行可能）:
- コスト: Bool=1, Int=8, Float=8, Trigger=1, `synced=False`→0, 未知型→ValueError。
- 予算: 32×Float(=256bit) は ちょうど予算内、+1 Bool で over_budget=True、remaining 計算が正しい。
- 提案: 二値 Float があれば Bool 化提案を含む。予算内なら提案は空。

## 6. 参照
- [`IMPROVEMENT_BACKLOG.md`](IMPROVEMENT_BACKLOG.md) / [`CATEGORY_RESEARCH.md`](CATEGORY_RESEARCH.md) / [`IMPROVEMENT_ROADMAP.md`](IMPROVEMENT_ROADMAP.md)（項目 #12）
