# 仕様書: VRChat パフォーマンスアナライザー

**版**: 1.0 / **作成日**: 2026-06-07 / **対象**: `main/vrchat_performance_analyzer.py`
**目的**: ファイルI/O 依存の分析ロジックを分離し、ユニットテスト可能にする。

## 1. 現状とギャップ

- **GAP-1**: **分析ロジックがファイルI/O に結合している**: `analyze_preset(preset_path)` は
  JSON を読み込んでから分析する一体化メソッドのため、`AvatarStats` を直接渡す
  ユニットテストが書けない。純粋な分析ロジックが外部から利用できない。
- **GAP-2**: **`_generate_suggestions` の KeyError リスク**: `target_rank = PerformanceRank.GOOD`
  で `self.limits_db[target_rank]` を参照するが、iOS など limits_db に GOOD が無い
  プラットフォームを追加したとき `KeyError` になる。

## 2. 要件

| ID | 要件 | 状況 | 実装 |
|---|---|---|---|
| REQ-VP-01 | `AvatarStats` を受け取る純粋分析 API | ✅ 実装済 | `analyze_stats(stats)` |
| REQ-VP-02 | `analyze_preset` は `analyze_stats` を内部で呼ぶ（DRY） | ✅ 実装済 | リファクタリング |
| REQ-VP-03 | `_generate_suggestions` の KeyError ガード | ✅ 実装済 | `limits_db.get(target_rank)` |

## 3. 仕様詳細

### `analyze_stats(stats: AvatarStats) -> PerformanceAnalysisResult`（REQ-VP-01）
- `analyze_preset` と同じロジックで分析を行うが、ファイル読み込みなし。
- `details["preset_path"]` は `None`。
- 例外なしで `PerformanceAnalysisResult` を返す。

### `analyze_preset` リファクタリング（REQ-VP-02）
```python
def analyze_preset(self, preset_path):
    with open(preset_path, ...) as f:
        preset_data = json.load(f)
    stats = self._extract_avatar_stats(preset_data)
    result = self.analyze_stats(stats)
    result.details['preset_path'] = str(preset_path)
    return result
```

### `_generate_suggestions` ガード（REQ-VP-03）
```python
target_limits = self.limits_db.get(target_rank)
if target_limits is None:
    return []  # limits_db にターゲットランクがない場合は提案なし
```

## 4. 受け入れ基準（テスト）

`tests/test_vrchat_analyzer.py`（stdlib unittest, ファイル不要, 本環境で実行可能）:
- `analyze_stats` でランク判定（EXCELLENT/GOOD/MEDIUM/POOR/VERY_POOR）
- `analyze_stats` でスコア範囲 [0, 100]
- ライト存在でスコアにペナルティ
- 最適化提案の生成
- Android プラットフォームでの動作確認
