# 仕様書: joint_range_report

**版**: 1.0 / **作成日**: 2026-06-08 / **対象**: `main/joint_range_report.py`
**目的**: ジョイント可動域レポートの機能検証。

## 1. 現状とギャップ

コードは正常。ギャップなし。テストカバレッジが欠如。

## 2. 要件

要件変更なし。

## 3. 受け入れ基準（テスト）

`tests/test_joint_range_report.py`（stdlib unittest のみ）:
- `generate_joint_range_report()` が `(header, rows)` タプルを返す
- header は `["体型"] + joint_names`
- 行の各セルが `"nn.n"` 形式の文字列
- `report_as_records()` がリストを返す
- カスタム関節名を指定できる
- `print_report_table()` が空の rows でもクラッシュしない
