# 仕様書: VRChatPerformanceAnalyzer 改善 (同種OSS比較)

**版**: 2.0 / **作成日**: 2026-06-08 / **対象**: `main/vrchat_performance_analyzer.py`
**目的**: VRChat 公式ランキング方式・Thry's Avatar Performance Tools・d4rkAvatarOptimizer との比較で判明したギャップを実装。

## 参考にした同種ソフト

- VRChat 公式 Avatar Performance Ranking System（総合ランク = 全カテゴリ中の最悪ランク）
- [Thryrallo/VRC-Avatar-Performance-Tools](https://github.com/Thryrallo/VRC-Avatar-Performance-Tools)（テクスチャ VRAM 算出）
- [d4rkc0d3r/d4rkAvatarOptimizer](https://github.com/d4rkc0d3r/d4rkAvatarOptimizer)（マテリアル/メッシュ削減）

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-VP-04 | `_meets_limits()` が 22 次元中 9 次元しか評価しない（material_slots, physbones_transforms/colliders/collision_checks, animators, trail/line_renderers, cloths, cloth_vertices, physics_colliders/rigidbodies, audio_sources を無視） | VRChat 公式は「全カテゴリ中の最悪ランク」で総合判定する。例えば physbones_transforms=256（POOR 相当）でも Cocoa は GOOD と誤判定し得る |
| GAP-VP-05 | 総合ランクのボトルネック次元を特定・報告しない | Thry's/VRChat SDK は律速ステータスを明示する。ユーザーは「なぜ MEDIUM なのか」が分からない |
| GAP-VP-06 | テクスチャ VRAM 推定が旧フォーマット（RGBA32/RGB24/DXT1/DXT5）のみ | BC7・BC5（法線）・ASTC（Quest）など現行フォーマット未対応で VRAM を過大/過小評価 |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-VP-04 | `_meets_limits()` は `PerformanceLimits` の全 22 次元を評価する（AND で「全て制限内」= そのランクを満たす） | `LIMIT_FIELDS` を定義し getattr で汎用判定 |
| REQ-VP-05 | `get_limiting_factors(stats) -> List[Dict]` を追加し、総合ランクと一致する（=律速している）次元を返す。`analyze_stats` の `details['limiting_factors']` に格納し、レポートにも表示 | 各次元の単独ランクを `_rank_for_value` で算出し最悪ランクと比較 |
| REQ-VP-06 | テクスチャフォーマット表に BC7=1.0, BC5=1.0, BC1=0.5, BC3=1.0, ASTC_4x4=1.0, ASTC_6x6≈0.44, ASTC_8x8=0.25 bpp を追加 | 大文字小文字を正規化して照合 |

## 3. 受け入れ基準（テスト）

`tests/test_vrchat_analyzer.py` に追加（既存16件は維持）:
- physbones_transforms 単独が POOR 相当なら、他が EXCELLENT でも総合 POOR（REQ-VP-04）
- audio_sources 超過が総合ランクを下げる
- `get_limiting_factors()` が律速次元名を返す
- 全次元が EXCELLENT のとき limiting_factors は空
- `details['limiting_factors']` が分析結果に含まれる
- BC7/ASTC_8x8 フォーマットのテクスチャ VRAM が正しく算出される
- フォーマット名の大文字小文字を問わない
- レポートに律速要因セクションが含まれる（ボトルネックがある場合）
