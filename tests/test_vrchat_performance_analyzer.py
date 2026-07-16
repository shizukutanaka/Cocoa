"""Tests for main/vrchat_performance_analyzer.py."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "main"))

from vrchat_performance_analyzer import (
    AvatarStats,
    PerformanceRank,
    Platform,
    VRChatPerformanceAnalyzer,
    analyze_all_platforms,
    generate_cross_platform_report,
    worst_platform_rank,
)


def _excellent_stats():
    """Stats that should achieve Excellent rank on PC."""
    return AvatarStats(
        polygons=5000,
        materials=1,
        bones=50,
        skinned_meshes=1,
        mesh_count=1,
        material_slots=1,
        physbones_components=2,
        physbones_transforms=8,
        physbones_colliders=2,
        physbones_collision_checks=4,
        animators=1,
        lights=0,
        particle_systems=0,
        particle_max_particles=0,
        trail_renderers=0,
        line_renderers=0,
        cloths=0,
        cloth_vertices=0,
        physics_colliders=0,
        physics_rigidbodies=0,
        audio_sources=0,
        texture_memory_mb=10.0,
    )


def _very_poor_stats():
    """Stats that exceed all limits → Very Poor rank."""
    return AvatarStats(
        polygons=500_000,
        materials=50,
        bones=1000,
        skinned_meshes=20,
        mesh_count=50,
        material_slots=50,
        physbones_components=50,
        physbones_transforms=500,
        physbones_colliders=100,
        physbones_collision_checks=1000,
        animators=20,
        lights=10,
        particle_systems=30,
        particle_max_particles=100000,
        trail_renderers=20,
        line_renderers=20,
        cloths=10,
        cloth_vertices=50000,
        physics_colliders=50,
        physics_rigidbodies=50,
        audio_sources=20,
        texture_memory_mb=1000.0,
    )


class TestVRChatPerformanceAnalyzer(unittest.TestCase):

    def setUp(self):
        self.pc_analyzer = VRChatPerformanceAnalyzer(platform=Platform.PC)
        self.android_analyzer = VRChatPerformanceAnalyzer(platform=Platform.ANDROID)

    def test_excellent_stats_get_good_or_better_rank(self):
        result = self.pc_analyzer.analyze_stats(_excellent_stats())
        self.assertIn(result.rank, [PerformanceRank.EXCELLENT, PerformanceRank.GOOD])

    def test_very_poor_stats_get_poor_rank(self):
        result = self.pc_analyzer.analyze_stats(_very_poor_stats())
        self.assertEqual(result.rank, PerformanceRank.VERY_POOR)

    def test_result_has_correct_platform(self):
        result = self.pc_analyzer.analyze_stats(_excellent_stats())
        self.assertEqual(result.platform, Platform.PC)

    def test_android_is_stricter_than_pc(self):
        stats = _excellent_stats()
        pc_result = self.pc_analyzer.analyze_stats(stats)
        android_result = self.android_analyzer.analyze_stats(stats)
        pc_rank_idx = list(PerformanceRank).index(pc_result.rank)
        android_rank_idx = list(PerformanceRank).index(android_result.rank)
        self.assertLessEqual(pc_rank_idx, android_rank_idx)

    def test_score_in_range(self):
        result = self.pc_analyzer.analyze_stats(_excellent_stats())
        self.assertGreaterEqual(result.score, 0.0)
        self.assertLessEqual(result.score, 100.0)

    def test_issues_is_list(self):
        result = self.pc_analyzer.analyze_stats(_very_poor_stats())
        self.assertIsInstance(result.issues, list)
        self.assertGreater(len(result.issues), 0)

    def test_suggestions_is_list(self):
        result = self.pc_analyzer.analyze_stats(_very_poor_stats())
        self.assertIsInstance(result.suggestions, list)

    def test_avatar_stats_preserved(self):
        stats = _excellent_stats()
        result = self.pc_analyzer.analyze_stats(stats)
        self.assertEqual(result.avatar_stats.polygons, stats.polygons)

    def test_default_platform_is_pc(self):
        analyzer = VRChatPerformanceAnalyzer()
        self.assertEqual(analyzer.platform, Platform.PC)

    def test_compliant_flag_set(self):
        result = self.pc_analyzer.analyze_stats(_excellent_stats())
        self.assertIn("is_vrchat_compliant", result.details)


class TestAnalyzeAllPlatforms(unittest.TestCase):

    def test_returns_pc_and_android_by_default(self):
        stats = _excellent_stats()
        results = analyze_all_platforms(stats)
        self.assertIn("pc", results)
        self.assertIn("android", results)

    def test_custom_platforms(self):
        stats = _excellent_stats()
        results = analyze_all_platforms(stats, platforms=[Platform.PC])
        self.assertIn("pc", results)
        self.assertNotIn("android", results)

    def test_all_results_have_rank(self):
        results = analyze_all_platforms(_excellent_stats())
        for result in results.values():
            self.assertIsInstance(result.rank, PerformanceRank)


class TestWorstPlatformRank(unittest.TestCase):

    def test_excellent_everywhere(self):
        analyzer = VRChatPerformanceAnalyzer()
        result = analyzer.analyze_stats(_excellent_stats())
        results = {"pc": result}
        rank = worst_platform_rank(results)
        self.assertIsInstance(rank, PerformanceRank)

    def test_worst_is_very_poor_when_any_is_very_poor(self):
        pc_result = VRChatPerformanceAnalyzer(Platform.PC).analyze_stats(_very_poor_stats())
        results = {"pc": pc_result}
        rank = worst_platform_rank(results)
        self.assertEqual(rank, PerformanceRank.VERY_POOR)


class TestGenerateCrossPlatformReport(unittest.TestCase):

    def test_report_is_string(self):
        results = analyze_all_platforms(_excellent_stats())
        report = generate_cross_platform_report(results)
        self.assertIsInstance(report, str)

    def test_report_contains_platforms(self):
        results = analyze_all_platforms(_excellent_stats())
        report = generate_cross_platform_report(results)
        self.assertIn("PC", report)
        self.assertIn("ANDROID", report)

    def test_report_contains_effective_rank(self):
        results = analyze_all_platforms(_excellent_stats())
        report = generate_cross_platform_report(results)
        self.assertIn("Effective rank", report)


if __name__ == "__main__":
    unittest.main()
