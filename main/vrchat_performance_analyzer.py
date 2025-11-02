#!/usr/bin/env python3
"""
VRChat Performance Analyzer
VRChat公式基準に基づくアバタープリセット性能評価システム

参考: https://creators.vrchat.com/avatars/avatar-performance-ranking-system/
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
import json
import logging
from pathlib import Path

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


@dataclass
class PerformanceAnalysisResult:
    """性能分析結果"""
    rank: PerformanceRank
    platform: Platform
    avatar_stats: AvatarStats
    issues: List[Dict[str, any]]
    suggestions: List[OptimizationSuggestion]
    score: float  # 0-100
    details: Dict[str, any]


class VRChatPerformanceAnalyzer:
    """VRChat公式基準に基づくアバター性能評価"""

    def __init__(self, platform: Platform = Platform.PC):
        self.platform = platform
        self.limits_db = (
            VRChatPerformanceLimits.PC_LIMITS if platform == Platform.PC
            else VRChatPerformanceLimits.ANDROID_LIMITS
        )

    def analyze_preset(self, preset_path: Path) -> PerformanceAnalysisResult:
        """プリセットファイルを解析してパフォーマンスランクを評価"""
        try:
            # プリセットファイル読み込み
            with open(preset_path, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)

            # アバター統計情報を抽出
            stats = self._extract_avatar_stats(preset_data)

            # パフォーマンスランクを計算
            rank = self._calculate_rank(stats)

            # 問題を検出
            issues = self._detect_issues(stats)

            # 最適化提案を生成
            suggestions = self._generate_suggestions(stats, rank)

            # スコア計算
            score = self._calculate_score(stats, rank)

            return PerformanceAnalysisResult(
                rank=rank,
                platform=self.platform,
                avatar_stats=stats,
                issues=issues,
                suggestions=suggestions,
                score=score,
                details={
                    'preset_path': str(preset_path),
                    'target_rank': PerformanceRank.GOOD.value,
                    'is_vrchat_compliant': len([i for i in issues if i['severity'] == 'critical']) == 0
                }
            )

        except Exception as e:
            logger.error(f"Failed to analyze preset: {e}")
            raise

    def _extract_avatar_stats(self, preset_data: dict) -> AvatarStats:
        """プリセットデータからアバター統計を抽出"""
        stats = AvatarStats()

        # アバターデータから統計を抽出
        # 実際のプリセットフォーマットに応じて調整が必要
        avatar_data = preset_data.get('avatar', {})

        stats.polygons = avatar_data.get('polygon_count', 0)
        stats.materials = avatar_data.get('material_count', 0)
        stats.bones = avatar_data.get('bone_count', 0)
        stats.skinned_meshes = avatar_data.get('skinned_mesh_count', 0)
        stats.mesh_count = avatar_data.get('mesh_count', 0)
        stats.lights = avatar_data.get('light_count', 0)
        stats.particle_systems = avatar_data.get('particle_system_count', 0)
        stats.physbones_components = avatar_data.get('physbones_count', 0)

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

            # フォーマット別のバイト数
            bytes_per_pixel = {
                'RGBA32': 4,
                'RGB24': 3,
                'DXT1': 0.5,  # 圧縮
                'DXT5': 1.0   # 圧縮
            }.get(format_type, 4)

            # メモリ使用量計算（ミップマップ込み: 1.33倍）
            memory_bytes = width * height * bytes_per_pixel * 1.33
            total_mb += memory_bytes / (1024 * 1024)

        return total_mb

    def _calculate_rank(self, stats: AvatarStats) -> PerformanceRank:
        """統計からパフォーマンスランクを計算"""
        # 各ランクの制限値と比較
        for rank in [PerformanceRank.EXCELLENT, PerformanceRank.GOOD,
                     PerformanceRank.MEDIUM, PerformanceRank.POOR]:
            limits = self.limits_db[rank]

            # すべての制限値を満たしているかチェック
            if self._meets_limits(stats, limits):
                return rank

        return PerformanceRank.VERY_POOR

    def _meets_limits(self, stats: AvatarStats, limits: PerformanceLimits) -> bool:
        """統計が制限値を満たしているかチェック"""
        return (
            stats.polygons <= limits.polygons and
            stats.materials <= limits.materials and
            stats.bones <= limits.bones and
            stats.skinned_meshes <= limits.skinned_meshes and
            stats.mesh_count <= limits.mesh_count and
            stats.physbones_components <= limits.physbones_components and
            stats.lights <= limits.lights and
            stats.particle_systems <= limits.particle_systems and
            stats.texture_memory_mb <= limits.texture_memory_mb
        )

    def _detect_issues(self, stats: AvatarStats) -> List[Dict[str, any]]:
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
        target_limits = self.limits_db[target_rank]

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
