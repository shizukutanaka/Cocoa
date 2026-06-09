# 仕様書: VRChatPerformanceAnalyzer 改善 v4（プリセット抽出の全次元対応）

**版**: 4.0 / **作成日**: 2026-06-08 / **対象**: `main/vrchat_performance_analyzer.py`
**目的**: v2 で `_meets_limits` が全 22 次元を評価するようになったが、`_extract_avatar_stats`
が 8 次元しか読み取らず、`analyze_preset()`（ファイル解析）が新ランキングの恩恵を受けられない
不整合を解消する。

## 1. 現状とギャップ

| ID | 問題 | 影響 |
|---|---|---|
| GAP-VP-09 | `_extract_avatar_stats()` が 22 次元中 8 次元（polygons/materials/bones/skinned_meshes/mesh_count/lights/particle_systems/physbones_components）しかプリセットから読まない | physbones_transforms/colliders、physics_colliders、audio_sources、cloth 等がプリセット解析で常に 0 になり、ファイル経由の全次元ランキングが機能しない |

## 2. 要件

| ID | 要件 | 実装 |
|---|---|---|
| REQ-VP-09 | `_extract_avatar_stats()` は全 22 次元をプリセットから読み取る | フィールド→キー候補のマッピングで汎用抽出 |
| REQ-VP-10 | 既存キー（`physbones_count` 等）は後方互換で動作する | キー候補リストに旧名を含める |
| REQ-VP-11 | 欠落キーは 0（texture は 0.0）にフォールバック | `AvatarStats` 既定値を維持 |

## 抽出キー対応表（候補順）

| フィールド | 受理キー |
|---|---|
| polygons | polygon_count, polygons |
| materials | material_count, materials |
| bones | bone_count, bones |
| skinned_meshes | skinned_mesh_count, skinned_meshes |
| mesh_count | mesh_count |
| material_slots | material_slot_count, material_slots |
| physbones_components | physbones_count, physbones_component_count, physbones_components |
| physbones_transforms | physbones_transform_count, physbones_transforms |
| physbones_colliders | physbones_collider_count, physbones_colliders |
| physbones_collision_checks | physbones_collision_check_count, physbones_collision_checks |
| animators | animator_count, animators |
| lights | light_count, lights |
| particle_systems | particle_system_count, particle_systems |
| particle_max_particles | particle_max_particles, max_particles |
| trail_renderers | trail_renderer_count, trail_renderers |
| line_renderers | line_renderer_count, line_renderers |
| cloths | cloth_count, cloths |
| cloth_vertices | cloth_vertex_count, cloth_vertices |
| physics_colliders | physics_collider_count, physics_colliders |
| physics_rigidbodies | physics_rigidbody_count, physics_rigidbodies |
| audio_sources | audio_source_count, audio_sources |
| texture_memory_mb | textures[] から推定 |

## 3. 受け入れ基準（テスト）

`tests/test_vrchat_analyzer.py` に追加（既存47件は維持）:
- 旧キー（physbones_count 等）でプリセットを解析できる（後方互換）
- 新次元（physbones_transform_count 等）がプリセットから読み取れる
- 欠落次元は 0 にフォールバック
- 新キーで physbones_transforms=256 のプリセットが POOR になる（全次元ランキングが効く）
- テクスチャ込みのフルプリセットが正しく解析される
