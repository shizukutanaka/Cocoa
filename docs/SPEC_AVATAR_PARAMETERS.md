# 仕様書: アバターパラメータ & 関節可動域レポート

**版**: 1.0 / **作成日**: 2026-06-07
**対象**: `main/avatar_parameters.py`, `main/avatar_parameter_sets.py`, `main/joint_range_report.py`
**目的**: パラメータ検証・プリセット取得安全性・レポート出力の要件を明文化し実装する。

## 1. 現状とギャップ

### avatar_parameters.py
- **GAP-1**: `AvatarParameters` に `__post_init__` バリデーションが無い。
  `muscle_mass=2.0`（>1.0）や `height=-10`（<=0）を渡しても何も起きない。

### avatar_parameter_sets.py
- **GAP-2**: `get_preset(name)` は不明な名前に対して `None` を返す（例外なし）。
  呼び出し元が None チェックを怠ると `AttributeError` が発生する。

### joint_range_report.py
- **GAP-3**: `generate_joint_range_report` は `get_preset` が `None` を返した場合の
  ガードが無く、`estimate_joint_range(joint, None)` で `AttributeError` になる。
- **GAP-4**: レポートの出力形式がプリント専用。
  構造化データ（dict リスト）を返す `report_as_records()` が無い。

## 2. 要件

| ID | 要件 | 状況 | 実装 |
|---|---|---|---|
| REQ-AP-01 | 身長・体重・muscle_mass・flexibility の範囲チェック | ✅ 実装済 | `AvatarParameters.__post_init__` |
| REQ-AP-02 | `estimate_joint_range` の上限チェック（360 deg） | ✅ 実装済 | `min(..., 360)` |
| REQ-AP-03 | `get_preset` の安全な取得（Not Found → KeyError） | ✅ 実装済 | `get_preset` 改修 |
| REQ-AP-04 | `generate_joint_range_report` の None プリセットガード | ✅ 実装済 | スキップ or エラー記録 |
| REQ-AP-05 | 構造化レポート出力 (`report_as_records`) | ✅ 実装済 | `joint_range_report.report_as_records` |

## 3. 仕様詳細

### `AvatarParameters.__post_init__`（REQ-AP-01）
- `height > 0`（単位: cm）。違反 → `ValueError("height must be > 0")`
- `weight > 0`（単位: kg）。違反 → `ValueError("weight must be > 0")`
- `0.0 <= muscle_mass <= 1.0`。違反 → `ValueError("muscle_mass must be in [0, 1]")`
- `0.0 <= flexibility <= 1.0`。違反 → `ValueError("flexibility must be in [0, 1]")`

### `estimate_joint_range`（REQ-AP-02）
- 戻り値は `max(30, min(360, base + factors))` に制限。

### `get_preset(name)`（REQ-AP-03）
- 名前が不明なとき `KeyError(name)` を送出（`None` を返さない）。

### `generate_joint_range_report`（REQ-AP-04）
- `get_preset(preset_name)` が `KeyError` を送出したとき、そのプリセットをスキップし
  ログ警告を出す（クラッシュしない）。

### `report_as_records(joint_names=None) -> list[dict]`（REQ-AP-05）
- 各プリセットを `{"preset": name, "shoulder": deg, "elbow": deg, ...}` の dict として返す。
- `joint_names` が `None` のとき `['shoulder', 'elbow', 'knee']` を使用。

## 4. 受け入れ基準（テスト）
`tests/test_avatar_parameters.py`（stdlib unittest, 本環境で実行可能）。
