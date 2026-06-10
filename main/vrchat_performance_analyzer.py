#!/usr/bin/env python3
"""
VRChat Performance Analyzer
VRChat公式基準に基づくアバタープリセット性能評価システム

参考: https://creators.vrchat.com/avatars/avatar-performance-ranking-system/
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PerformanceRank(Enum):
    """VRChatパフォーマンスランク"""
    EXCELLENT = "excellent"
    GOOD = "good"
    MEDIUM = "medium"
    POOR = "poor"
    VERY_POOR = "very_poor"


class Platform(Enum):
    """対応プラットフォーム"""
    PC = "pc"
    ANDROID = "android"
    IOS = "ios"


@dataclass
class PerformanceLimits:
    """パフォーマンス制限値"""
    polygons: int
    materials: int
    bones: int
    skinned_meshes: int
    mesh_count: int
    material_slots: int
    physbones_components: int
    physbones_transforms: int
    physbones_colliders: int
    physbones_collision_checks: int
    animators: int
    lights: int
    particle_systems: int
    particle_max_particles: int
    trail_renderers: int
    line_renderers: int
    cloths: int
    cloth_vertices: int
    physics_colliders: int
    physics_rigidbodies: int
    audio_sources: int
    texture_memory_mb: int


class VRChatPerformanceLimits:
    """VRChat公式パフォーマンス制限値データベース"""

    # PC版制限値
    PC_LIMITS = {
        PerformanceRank.EXCELLENT: PerformanceLimits(
            polygons=7500,
            materials=1,
            bones=75,
            skinned_meshes=1,
            mesh_count=2,
            material_slots=1,
            physbones_components=4,
            physbones_transforms=16,
            physbones_colliders=4,
            physbones_collision_checks=8,
            animators=1,
            lights=0,  # VRChat公式: Lightsは一切使用しない
            particle_systems=1,
            particle_max_particles=200,
            trail_renderers=1,
            line_renderers=0,
            cloths=0,
            cloth_vertices=0,
            physics_colliders=1,
            physics_rigidbodies=1,
            audio_sources=1,
            texture_memory_mb=10
        ),
        PerformanceRank.GOOD: PerformanceLimits(
            polygons=10000,
            materials=4,
            bones=150,
            skinned_meshes=2,
            mesh_count=4,
            material_slots=4,
            physbones_components=8,
            physbones_transforms=64,
            physbones_colliders=8,
            physbones_collision_checks=32,
            animators=4,
            lights=0,  # VRChat公式: Lightsは一切使用しない
            particle_systems=4,
            particle_max_particles=1000,
            trail_renderers=2,
            line_renderers=1,
            cloths=1,
            cloth_vertices=100,
            physics_colliders=4,
            physics_rigidbodies=4,
            audio_sources=4,
            texture_memory_mb=40
        ),
        PerformanceRank.MEDIUM: PerformanceLimits(
            polygons=15000,
            materials=8,
            bones=256,
            skinned_meshes=4,
            mesh_count=8,
            material_slots=8,
            physbones_components=16,
            physbones_transforms=128,
            physbones_colliders=16,
            physbones_collision_checks=64,
            animators=16,
            lights=0,  # VRChat公式: Lightsは一切使用しない
            particle_systems=8,
            particle_max_particles=2500,
            trail_renderers=4,
            line_renderers=2,
            cloths=1,
            cloth_vertices=200,
            physics_colliders=8,
            physics_rigidbodies=8,
            audio_sources=8,
            texture_memory_mb=75
        ),
        PerformanceRank.POOR: PerformanceLimits(
            polygons=20000,
            materials=16,
            bones=400,
            skinned_meshes=8,
            mesh_count=16,
            material_slots=16,
            physbones_components=32,
            physbones_transforms=256,
            physbones_colliders=32,
            physbones_collision_checks=256,
            animators=32,
            lights=0,  # VRChat公式: Lightsは一切使用しない
            particle_systems=16,
            particle_max_particles=5000,
            trail_renderers=8,
            line_renderers=4,
            cloths=1,
            cloth_vertices=500,
            physics_colliders=16,
            physics_rigidbodies=16,
            audio_sources=16,
            texture_memory_mb=150
        )
    }

    # Android/Quest版制限値（より厳しい）
    ANDROID_LIMITS = {
        PerformanceRank.EXCELLENT: PerformanceLimits(
            polygons=5000,
            materials=1,
            bones=75,
            skinned_meshes=1,
            mesh_count=2,
            material_slots=1,
            physbones_components=2,
            physbones_transforms=8,
            physbones_colliders=2,
            physbones_collision_checks=4,
            animators=1,
            lights=0,
            particle_systems=1,
            particle_max_particles=100,
            trail_renderers=0,
            line_renderers=0,
            cloths=0,
            cloth_vertices=0,
            physics_colliders=0,
            physics_rigidbodies=0,
            audio_sources=1,
            texture_memory_mb=5
        ),
        PerformanceRank.GOOD: PerformanceLimits(
            polygons=7500,
            materials=2,
            bones=90,
            skinned_meshes=1,
            mesh_count=2,
            material_slots=2,
            physbones_components=4,
            physbones_transforms=16,
            physbones_colliders=4,
            physbones_collision_checks=8,
            animators=2,
            lights=0,
            particle_systems=2,
            particle_max_particles=200,
            trail_renderers=1,
            line_renderers=0,
            cloths=0,
            cloth_vertices=0,
            physics_colliders=1,
            physics_rigidbodies=1,
            audio_sources=2,
            texture_memory_mb=10
        ),
        PerformanceRank.MEDIUM: PerformanceLimits(
            polygons=10000,
            materials=4,
            bones=150,
            skinned_meshes=2,
            mesh_count=4,
            material_slots=4,
            physbones_components=8,
            physbones_transforms=32,
            physbones_colliders=8,
            physbones_collision_checks=16,
            animators=4,
            lights=0,
            particle_systems=4,
            particle_max_particles=500,
            trail_renderers=2,
            line_renderers=0,
            cloths=0,
            cloth_vertices=0,
            physics_colliders=2,
            physics_rigidbodies=2,
            audio_sources=4,
            texture_memory_mb=20
        )
    }


@dataclass
class AvatarStats:
    """アバター統計情報"""
    polygons: int = 0
    materials: int = 0
    bones: int = 0
    skinned_meshes: int = 0
    mesh_count: int = 0
    material_slots: int = 0
    physbones_components: int = 0
    physbones_transforms: int = 0
    physbones_colliders: int = 0
    physbones_collision_checks: int = 0
    animators: int = 0
    lights: int = 0
    particle_systems: int = 0
    particle_max_particles: int = 0
    trail_renderers: int = 0
    line_renderers: int = 0
    cloths: int = 0
    cloth_vertices: int = 0
    physics_colliders: int = 0
    physics_rigidbodies: int = 0
    audio_sources: int = 0
    texture_memory_mb: float = 0.0


@dataclass
class OptimizationSuggestion:
    """最適化提案"""
    category: str
    severity: str  # critical, warning, info
    current_value: int
    target_value: int
    suggestion: str
    action: str
    reference_url: Optional[str] = None
    reduction: int = 0  # 削減量 (current_value - target_value); __post_init__ で算出

    def __post_init__(self):
        # 削減量を自動算出（負値にはしない）
        self.reduction = max(0, self.current_value - self.target_value)


@dataclass
class PerformanceAnalysisResult:
    """性能分析結果"""
    rank: PerformanceRank
    platform: Platform
    avatar_stats: AvatarStats
    issues: List[Dict[str, Any]]
    suggestions: List[OptimizationSuggestion]
    score: float  # 0-100
    details: Dict[str, Any]


class VRChatPerformanceAnalyzer:
    """VRChat公式基準に基づくアバター性能評価"""

    def __init__(self, platform: Platform = Platform.PC):
        self.platform = platform
        self.limits_db = (
            VRChatPerformanceLimits.PC_LIMITS if platform == Platform.PC
            else VRChatPerformanceLimits.ANDROID_LIMITS
        )

    def analyze_stats(self, stats: AvatarStats) -> PerformanceAnalysisResult:
        """Pure stats analysis (no file I/O). Returns a PerformanceAnalysisResult."""
        rank = self._calculate_rank(stats)
        issues = self._detect_issues(stats)
        suggestions = self._generate_suggestions(stats, rank)
        score = self._calculate_score(stats, rank)
        return PerformanceAnalysisResult(
            rank=rank,
            platform=self.platform,
            avatar_stats=stats,
            issues=issues,
            suggestions=suggestions,
            score=score,
            details={
                'preset_path': None,
                'target_rank': PerformanceRank.GOOD.value,
                'is_vrchat_compliant': len([i for i in issues if i['severity'] == 'critical']) == 0,
                'limiting_factors': self.get_limiting_factors(stats),
            }
        )

    def analyze_preset(self, preset_path: Path) -> PerformanceAnalysisResult:
        """プリセットファイルを解析してパフォーマンスランクを評価"""
        try:
            with open(preset_path, encoding='utf-8') as f:
                preset_data = json.load(f)
            stats = self._extract_avatar_stats(preset_data)
            result = self.analyze_stats(stats)
            result.details['preset_path'] = str(preset_path)
            return result
        except Exception as e:
            logger.error(f"Failed to analyze preset: {e}")
            raise

    # AvatarStats フィールド -> プリセットで受理するキー候補（先頭優先）。
    # 旧来の `*_count` キーを後方互換のため先頭に置く。
    STAT_KEY_ALIASES: Dict[str, tuple] = {
        'polygons': ('polygon_count', 'polygons'),
        'materials': ('material_count', 'materials'),
        'bones': ('bone_count', 'bones'),
        'skinned_meshes': ('skinned_mesh_count', 'skinned_meshes'),
        'mesh_count': ('mesh_count',),
        'material_slots': ('material_slot_count', 'material_slots'),
        'physbones_components': ('physbones_count', 'physbones_component_count', 'physbones_components'),
        'physbones_transforms': ('physbones_transform_count', 'physbones_transforms'),
        'physbones_colliders': ('physbones_collider_count', 'physbones_colliders'),
        'physbones_collision_checks': ('physbones_collision_check_count', 'physbones_collision_checks'),
        'animators': ('animator_count', 'animators'),
        'lights': ('light_count', 'lights'),
        'particle_systems': ('particle_system_count', 'particle_systems'),
        'particle_max_particles': ('particle_max_particles', 'max_particles'),
        'trail_renderers': ('trail_renderer_count', 'trail_renderers'),
        'line_renderers': ('line_renderer_count', 'line_renderers'),
        'cloths': ('cloth_count', 'cloths'),
        'cloth_vertices': ('cloth_vertex_count', 'cloth_vertices'),
        'physics_colliders': ('physics_collider_count', 'physics_colliders'),
        'physics_rigidbodies': ('physics_rigidbody_count', 'physics_rigidbodies'),
        'audio_sources': ('audio_source_count', 'audio_sources'),
    }

    def _extract_avatar_stats(self, preset_data: dict) -> AvatarStats:
        """プリセットデータからアバター統計を抽出（全 22 次元）。"""
        stats = AvatarStats()

        # アバターデータから統計を抽出
        # 実際のプリセットフォーマットに応じて調整が必要
        avatar_data = preset_data.get('avatar', {})

        for field, aliases in self.STAT_KEY_ALIASES.items():
            for key in aliases:
                if key in avatar_data:
                    setattr(stats, field, avatar_data[key])
                    break  # 先頭で見つかったキーを採用、欠落時は既定値(0)

        # テクスチャメモリ推定
        textures = avatar_data.get('textures', [])
        stats.texture_memory_mb = self._estimate_texture_memory(textures)

        return stats

    def _estimate_texture_memory(self, textures: List[dict]) -> float:
        """テクスチャメモリ使用量を推定"""
        total_mb = 0.0

        for texture in textures:
            width = texture.get('width', 1024)
            height = texture.get('height', 1024)
            format_type = texture.get('format', 'RGBA32')

            bytes_per_pixel = self._format_bytes_per_pixel(format_type)

            # メモリ使用量計算（ミップマップ込み: 1.33倍）
            memory_bytes = width * height * bytes_per_pixel * 1.33
            total_mb += memory_bytes / (1024 * 1024)

        return total_mb

    # フォーマット別バイト/ピクセル。圧縮フォーマットはブロック圧縮の実効値。
    # 参考: Unity TextureImporter / VRChat (Thry's Avatar Performance Tools)。
    FORMAT_BYTES_PER_PIXEL: Dict[str, float] = {
        # 非圧縮
        'RGBA32': 4.0,
        'ARGB32': 4.0,
        'RGB24': 3.0,
        'R8': 1.0,
        'RGBAHALF': 8.0,
        # 旧来のブロック圧縮 (DXT/BC)
        'DXT1': 0.5,   # = BC1
        'DXT5': 1.0,   # = BC3
        'BC1': 0.5,
        'BC3': 1.0,
        'BC4': 0.5,    # 単チャンネル
        'BC5': 1.0,    # 法線マップ向け 2 チャンネル
        'BC7': 1.0,    # 高品質 RGBA
        # ASTC (主に Quest/Android)
        'ASTC_4X4': 1.0,
        'ASTC_5X5': 0.64,
        'ASTC_6X6': 0.44,
        'ASTC_8X8': 0.25,
        'ASTC_10X10': 0.16,
        'ASTC_12X12': 0.11,
    }

    def _format_bytes_per_pixel(self, format_type: str) -> float:
        """テクスチャフォーマット名から実効バイト/ピクセルを返す（大文字小文字非依存）。

        未知フォーマットは安全側に倒して非圧縮 RGBA32 (4.0) を仮定する。
        """
        key = str(format_type).upper().replace('-', '_').replace(' ', '')
        return self.FORMAT_BYTES_PER_PIXEL.get(key, 4.0)

    # ベスト→ワーストのランク順序。総合ランクは全次元中の最悪ランク（VRChat 公式方式）。
    RANK_ORDER: List[PerformanceRank] = [
        PerformanceRank.EXCELLENT,
        PerformanceRank.GOOD,
        PerformanceRank.MEDIUM,
        PerformanceRank.POOR,
    ]

    # PerformanceLimits / AvatarStats で共通する評価対象フィールド（全 22 次元）。
    LIMIT_FIELDS: tuple = (
        'polygons', 'materials', 'bones', 'skinned_meshes', 'mesh_count',
        'material_slots', 'physbones_components', 'physbones_transforms',
        'physbones_colliders', 'physbones_collision_checks', 'animators',
        'lights', 'particle_systems', 'particle_max_particles',
        'trail_renderers', 'line_renderers', 'cloths', 'cloth_vertices',
        'physics_colliders', 'physics_rigidbodies', 'audio_sources',
        'texture_memory_mb',
    )

    def _calculate_rank(self, stats: AvatarStats) -> PerformanceRank:
        """統計からパフォーマンスランクを計算（全次元の最悪ランク）。"""
        for rank in self.RANK_ORDER:
            limits = self.limits_db.get(rank)
            if limits is None:
                continue
            if self._meets_limits(stats, limits):
                return rank
        return PerformanceRank.VERY_POOR

    def _meets_limits(self, stats: AvatarStats, limits: PerformanceLimits) -> bool:
        """統計が全 22 次元で制限値を満たしているかチェック。

        VRChat 公式のランク判定は「全カテゴリが当該ランクの制限内」のときのみ
        そのランクを満たす（= 総合ランクは最悪カテゴリで決まる）。
        """
        for field in self.LIMIT_FIELDS:
            if getattr(stats, field) > getattr(limits, field):
                return False
        return True

    def _rank_for_value(self, field: str, value: float) -> PerformanceRank:
        """単一次元の値が単独で達成するランクを返す。"""
        for rank in self.RANK_ORDER:
            limits = self.limits_db.get(rank)
            if limits is None:
                continue
            if value <= getattr(limits, field):
                return rank
        return PerformanceRank.VERY_POOR

    def get_limiting_factors(self, stats: AvatarStats) -> List[Dict[str, Any]]:
        """総合ランクを律速している次元（ボトルネック）を特定する。

        各次元の単独ランクを求め、総合（最悪）ランクと一致する次元を返す。
        全次元が EXCELLENT のときは空リスト。値が 0 の次元は除外する。
        """
        overall = self._calculate_rank(stats)
        if overall == PerformanceRank.EXCELLENT:
            return []

        worst_index = self.RANK_ORDER.index(overall) if overall in self.RANK_ORDER else len(self.RANK_ORDER)
        factors: List[Dict[str, Any]] = []
        for field in self.LIMIT_FIELDS:
            value = getattr(stats, field)
            if value <= 0:
                continue
            field_rank = self._rank_for_value(field, value)
            field_index = (
                self.RANK_ORDER.index(field_rank)
                if field_rank in self.RANK_ORDER else len(self.RANK_ORDER)
            )
            if field_index >= worst_index:
                factors.append({
                    'field': field,
                    'value': value,
                    'rank': field_rank.value,
                })
        return factors

    def _detect_issues(self, stats: AvatarStats) -> List[Dict[str, Any]]:
        """問題を検出"""
        issues = []

        # Lights使用チェック（VRChat公式: 一切使用しない）
        if stats.lights > 0:
            issues.append({
                'severity': 'critical',
                'category': 'Lights',
                'message': 'VRChat strongly recommends NOT using lights on avatars',
                'current': stats.lights,
                'target': 0,
                'reference': 'https://creators.vrchat.com/avatars/avatar-optimizing-tips/'
            })

        # PhysBones過剰使用チェック
        if stats.physbones_components > 8:
            issues.append({
                'severity': 'warning',
                'category': 'PhysBones',
                'message': f'Consider consolidating {stats.physbones_components} PhysBones components',
                'current': stats.physbones_components,
                'target': 8,
                'suggestion': 'Use multiple chains on fewer components'
            })

        # ポリゴン数チェック
        if stats.polygons > 15000:
            issues.append({
                'severity': 'warning',
                'category': 'Polygons',
                'message': f'Polygon count {stats.polygons} exceeds recommended Medium rank limit',
                'current': stats.polygons,
                'target': 15000
            })

        # テクスチャメモリチェック
        if stats.texture_memory_mb > 75:
            issues.append({
                'severity': 'warning',
                'category': 'Texture Memory',
                'message': f'Texture memory {stats.texture_memory_mb:.1f}MB exceeds recommended limit',
                'current': stats.texture_memory_mb,
                'target': 75
            })

        return issues

    def _generate_suggestions(self, stats: AvatarStats, rank: PerformanceRank) -> List[OptimizationSuggestion]:
        """最適化提案を生成"""
        suggestions = []

        # 目標ランク（Goodを目指す）
        target_rank = PerformanceRank.GOOD
        target_limits = self.limits_db.get(target_rank)
        if target_limits is None:
            return suggestions

        # ポリゴン数最適化
        if stats.polygons > target_limits.polygons:
            suggestions.append(OptimizationSuggestion(
                category='Polygon Reduction',
                severity='warning',
                current_value=stats.polygons,
                target_value=target_limits.polygons,
                suggestion=f'Reduce polygon count from {stats.polygons} to {target_limits.polygons}',
                action='Use Decimate modifier, retopology, or optimize mesh geometry',
                reference_url='https://creators.vrchat.com/avatars/avatar-optimizing-tips/'
            ))

        # マテリアル統合
        if stats.materials > target_limits.materials:
            suggestions.append(OptimizationSuggestion(
                category='Material Optimization',
                severity='info',
                current_value=stats.materials,
                target_value=target_limits.materials,
                suggestion=f'Consolidate materials from {stats.materials} to {target_limits.materials}',
                action='Combine textures into texture atlases, merge materials where possible'
            ))

        # テクスチャ最適化
        if stats.texture_memory_mb > target_limits.texture_memory_mb:
            suggestions.append(OptimizationSuggestion(
                category='Texture Optimization',
                severity='warning',
                current_value=int(stats.texture_memory_mb),
                target_value=int(target_limits.texture_memory_mb),
                suggestion=f'Reduce texture memory from {stats.texture_memory_mb:.1f}MB to {target_limits.texture_memory_mb}MB',
                action='Use 2048x2048 or 1024x1024 textures with DXT1/DXT5 compression'
            ))

        # Lights削除
        if stats.lights > 0:
            suggestions.append(OptimizationSuggestion(
                category='Remove Lights',
                severity='critical',
                current_value=stats.lights,
                target_value=0,
                suggestion='Remove all lights from avatar',
                action='Delete all Light components - VRChat official recommendation',
                reference_url='https://creators.vrchat.com/avatars/avatar-optimizing-tips/'
            ))

        return suggestions

    def _calculate_score(self, stats: AvatarStats, rank: PerformanceRank) -> float:
        """パフォーマンススコアを計算（0-100）"""
        # ランク別の基本スコア
        base_scores = {
            PerformanceRank.EXCELLENT: 100,
            PerformanceRank.GOOD: 85,
            PerformanceRank.MEDIUM: 70,
            PerformanceRank.POOR: 50,
            PerformanceRank.VERY_POOR: 25
        }

        base_score = base_scores[rank]

        # Lightsペナルティ
        if stats.lights > 0:
            base_score -= 20  # 重大なペナルティ

        # 過剰PhysBonesペナルティ
        if stats.physbones_components > 16:
            base_score -= 10

        return max(0, min(100, base_score))

    def generate_report(self, result: PerformanceAnalysisResult) -> str:
        """人間が読める形式のレポートを生成"""
        report = []
        report.append("=" * 70)
        report.append("VRChat Avatar Performance Analysis Report")
        report.append("=" * 70)
        report.append(f"\nPlatform: {result.platform.value.upper()}")
        report.append(f"Performance Rank: {result.rank.value.upper()}")
        report.append(f"Performance Score: {result.score:.1f}/100")
        report.append(f"VRChat Compliant: {'✓ Yes' if result.details['is_vrchat_compliant'] else '✗ No'}")

        report.append("\n" + "-" * 70)
        report.append("Avatar Statistics")
        report.append("-" * 70)
        stats = result.avatar_stats
        report.append(f"Polygons: {stats.polygons:,}")
        report.append(f"Materials: {stats.materials}")
        report.append(f"Bones: {stats.bones}")
        report.append(f"Skinned Meshes: {stats.skinned_meshes}")
        report.append(f"PhysBones Components: {stats.physbones_components}")
        report.append(f"Lights: {stats.lights} {'❌ REMOVE' if stats.lights > 0 else '✓'}")
        report.append(f"Particle Systems: {stats.particle_systems}")
        report.append(f"Texture Memory: {stats.texture_memory_mb:.1f} MB")

        limiting_factors = result.details.get('limiting_factors', [])
        if limiting_factors:
            report.append("\n" + "-" * 70)
            report.append(f"Limiting Factors (bottlenecks for {result.rank.value.upper()} rank)")
            report.append("-" * 70)
            for factor in limiting_factors:
                report.append(
                    f"  • {factor['field']}: {factor['value']} "
                    f"(this stat alone = {factor['rank'].upper()})"
                )

        if result.issues:
            report.append("\n" + "-" * 70)
            report.append("Issues Detected")
            report.append("-" * 70)
            for issue in result.issues:
                severity_icon = "🔴" if issue['severity'] == 'critical' else "⚠️"
                report.append(f"\n{severity_icon} {issue['category']}")
                report.append(f"  {issue['message']}")
                report.append(f"  Current: {issue['current']} → Target: {issue['target']}")
                if 'suggestion' in issue:
                    report.append(f"  Suggestion: {issue['suggestion']}")

        if result.suggestions:
            report.append("\n" + "-" * 70)
            report.append("Optimization Suggestions")
            report.append("-" * 70)
            for i, suggestion in enumerate(result.suggestions, 1):
                report.append(f"\n{i}. {suggestion.category}")
                report.append(f"   Current: {suggestion.current_value} → Target: {suggestion.target_value}")
                report.append(f"   {suggestion.suggestion}")
                report.append(f"   Action: {suggestion.action}")
                if suggestion.reference_url:
                    report.append(f"   Reference: {suggestion.reference_url}")

        report.append("\n" + "=" * 70)
        report.append("Recommendation: Aim for GOOD or MEDIUM rank for best user experience")
        report.append("Reference: https://creators.vrchat.com/avatars/avatar-performance-ranking-system/")
        report.append("=" * 70)

        return "\n".join(report)


# ----------------------------------------------------------------------
# クロスプラットフォーム解析 (PC ↔ Quest/Android)
# VRChat アバターは複数プラットフォーム向けにアップロードされ、各々で
# 個別のランクが付く。最も厳しい (=最悪) ランクが実効的な体験を決める。
# ----------------------------------------------------------------------

_DEFAULT_CROSS_PLATFORMS = (Platform.PC, Platform.ANDROID)

# 最悪ランク判定用の順序（良い→悪い）。
_RANK_SEVERITY = [
    PerformanceRank.EXCELLENT,
    PerformanceRank.GOOD,
    PerformanceRank.MEDIUM,
    PerformanceRank.POOR,
    PerformanceRank.VERY_POOR,
]


def analyze_all_platforms(
    stats: AvatarStats,
    platforms: Optional[List[Platform]] = None,
) -> Dict[str, PerformanceAnalysisResult]:
    """同一の AvatarStats を複数プラットフォームで解析する。

    Args:
        stats: 解析対象のアバター統計。
        platforms: 対象プラットフォーム。未指定時は PC と Android。

    Returns:
        プラットフォーム値 ("pc"/"android"/"ios") をキーとする解析結果の dict。
    """
    if platforms is None:
        platforms = list(_DEFAULT_CROSS_PLATFORMS)
    results: Dict[str, PerformanceAnalysisResult] = {}
    for platform in platforms:
        analyzer = VRChatPerformanceAnalyzer(platform=platform)
        results[platform.value] = analyzer.analyze_stats(stats)
    return results


def worst_platform_rank(results: Dict[str, PerformanceAnalysisResult]) -> PerformanceRank:
    """全プラットフォーム中の最悪ランク（実効ランク）を返す。"""
    worst = PerformanceRank.EXCELLENT
    worst_index = 0
    for result in results.values():
        idx = _RANK_SEVERITY.index(result.rank)
        if idx > worst_index:
            worst_index = idx
            worst = result.rank
    return worst


def generate_cross_platform_report(results: Dict[str, PerformanceAnalysisResult]) -> str:
    """複数プラットフォームの解析結果を表形式でまとめる。"""
    lines = []
    lines.append("=" * 70)
    lines.append("VRChat Avatar Cross-Platform Performance Report")
    lines.append("=" * 70)
    lines.append(f"\n{'Platform':<12}{'Rank':<14}{'Score':<10}{'Compliant':<10}")
    lines.append("-" * 70)
    for platform_key, result in results.items():
        compliant = "Yes" if result.details.get('is_vrchat_compliant') else "No"
        lines.append(
            f"{platform_key.upper():<12}{result.rank.value.upper():<14}"
            f"{result.score:<10.1f}{compliant:<10}"
        )
    lines.append("-" * 70)
    effective = worst_platform_rank(results)
    lines.append(f"\nEffective rank (worst across platforms): {effective.value.upper()}")
    lines.append(
        "Note: avatars are gated by their worst platform. "
        "Optimize for Quest/Android to lift the effective rank."
    )
    lines.append("=" * 70)
    return "\n".join(lines)


def main():
    """テスト実行"""
    # サンプル使用例
    analyzer = VRChatPerformanceAnalyzer(platform=Platform.PC)

    # テストデータ
    test_preset = Path("test_avatar_preset.json")

    # プリセットが存在しない場合はサンプル作成
    if not test_preset.exists():
        sample_data = {
            "avatar": {
                "polygon_count": 18000,
                "material_count": 12,
                "bone_count": 180,
                "skinned_mesh_count": 3,
                "mesh_count": 5,
                "light_count": 2,  # 問題あり
                "particle_system_count": 6,
                "physbones_count": 10,
                "textures": [
                    {"width": 2048, "height": 2048, "format": "RGBA32"},
                    {"width": 2048, "height": 2048, "format": "RGBA32"},
                    {"width": 1024, "height": 1024, "format": "DXT5"}
                ]
            }
        }
        test_preset.write_text(json.dumps(sample_data, indent=2))

    # 分析実行
    result = analyzer.analyze_preset(test_preset)

    # レポート出力
    print(analyzer.generate_report(result))


if __name__ == "__main__":
    main()
