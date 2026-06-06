# 仕様書: プリセット変更履歴 & ロールバック サブシステム

**版**: 1.0 / **作成日**: 2026-06-05 / **対象**: `main/preset_change_history.py`
**目的**: 変更履歴の要件を明文化し、不足（ロールバック・バージョン取得・堅牢性）を実装する。

## 1. 現状とギャップ
`PresetChangeHistory` は JSONL 追記で変更を記録(`record_change`)し、反復(`iter_history`)・
表示(`print_history`)を提供。コード実査で次の不足を確認:
- **GAP-1**: **ロールバック機能が無い**（クラス名は履歴だが過去状態へ戻す手段が無い）。
- **GAP-2**: 任意バージョン/最新状態の取得 API が無い。
- **GAP-3**: `iter_history` が `json.loads(line)` を無防備に呼ぶ。1行でも壊れていると
  反復全体が例外でクラッシュ（堅牢性不足）。`entry["preset_name"]` も KeyError 余地あり。

## 2. データモデル
履歴エントリ（1行=1 JSON）: `{timestamp, preset_name, change_type, before, after, user, note}`。
`after` はその変更後のプリセット状態。

## 3. 要件
| ID | 要件 | 状況 | 実装 |
|---|---|---|---|
| REQ-PH-01 | 変更の記録（追記） | ✅ | `record_change` |
| REQ-PH-02 | 履歴の反復/表示 | ✅ | `iter_history` / `print_history` |
| REQ-PH-03 | 壊れた行をスキップする堅牢な読み込み | ✅ 実装済 | `iter_history`（try/except） |
| REQ-PH-04 | 履歴の materialize / 件数 | ✅ 実装済 | `get_history`, `count` |
| REQ-PH-05 | 最新状態の取得 | ✅ 実装済 | `latest_state` |
| REQ-PH-06 | 指定バージョン(after)の取得（負index対応） | ✅ 実装済 | `get_version` |
| REQ-PH-07 | ロールバック（過去状態を返し、rollbackイベントを記録） | ✅ 実装済 | `rollback` |

## 4. 仕様詳細
- **REQ-PH-03** `iter_history(preset_name=None)`: 空行と `JSONDecodeError` の行はスキップ。
  フィルタは `entry.get("preset_name")` で行う。
- **REQ-PH-04** `get_history(preset_name=None) -> list[dict]`、`count(preset_name=None) -> int`。
- **REQ-PH-05** `latest_state(preset_name=None) -> dict | None`: 最後のエントリの `after`、無ければ None。
- **REQ-PH-06** `get_version(preset_name, index) -> dict`: 時系列 index（負可）の `after`。
  履歴無し→`IndexError`。
- **REQ-PH-07** `rollback(preset_name, index, user=None, note=None) -> dict`:
  対象 index の `after` を返し、`change_type="rollback"` のエントリを追記
  （before=現在の最新 after, after=対象状態）。これにより `latest_state` は対象状態になる。

## 5. 受け入れ基準（テスト）
`tests/test_preset_history.py`（stdlib unittest, 一時ファイル使用, 本環境で実行可能）。
後方互換: 既存 `record_change`/`iter_history`/`print_history` のシグネチャは不変。

## 6. 参照
[`SPEC_PRESET_PARAMETERS.md`](SPEC_PRESET_PARAMETERS.md)（REQ-PM-04 履歴・ロールバック）
