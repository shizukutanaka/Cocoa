# 仕様書: VRChatPerformanceAnalyzer 改善 v3（クロスプラットフォーム＋削減量）

**版**: 3.0 / **作成日**: 2026-06-08 / **対象**: `main/vrchat_performance_analyzer.py`
**目的**: 同種OSS比較で残った2項目（PC↔Quest 比較、最適化削減量の定量化）を実装。

## 参考にした同種ソフト

- VRChat 公式（アバターは PC/Quest 双方でランク付けされ、UI に両方表示される）
- d4rkAvatarOptimizer（マテリアル/メッシュ削減後の削減量を提示）

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-VP-07 | 1 回の解析が単一プラットフォームのみ。PC と Quest を同時に比較できない | VRChat アバターの多くはクロスプラットフォーム。Quest ランクは別途解析が必要で見落とされやすい |
| GAP-VP-08 | `OptimizationSuggestion` が目標値を示すが、削減量（impact）を定量化しない | d4rk 等は「何 MB / 何ポリゴン削減」を提示。優先順位付けに必要 |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-VP-07 | モジュール関数 `analyze_all_platforms(stats, platforms=None) -> Dict[str, PerformanceAnalysisResult]` を追加 | 既定で PC と Android を解析。キーは `"pc"`, `"android"` |
| REQ-VP-08 | モジュール関数 `worst_platform_rank(results) -> PerformanceRank` を追加 | 全プラットフォーム中の最悪ランク（実効ランク）を返す |
| REQ-VP-09 | `generate_cross_platform_report(results) -> str` を追加 | プラットフォーム別ランク・スコア・実効ランクを表形式で表示 |
| REQ-VP-10 | `OptimizationSuggestion` に `reduction: int = 0` を追加し `current_value - target_value` を設定 | 各提案の削減量を定量化 |

## 3. 受け入れ基準（テスト）

`tests/test_vrchat_analyzer.py` に追加（既存35件は維持）:
- `analyze_all_platforms()` が pc/android キーを持つ dict を返す
- 各値が `PerformanceAnalysisResult`
- 同一 stats で Android のランクが PC 以下（同等以下に厳しい）
- `platforms` 引数でプラットフォームを限定できる
- `worst_platform_rank()` が最悪ランクを返す
- `generate_cross_platform_report()` が両プラットフォーム名を含む文字列を返す
- ポリゴン削減提案の `reduction` が `current - target` と一致
- 提案に `reduction` 属性が存在する
