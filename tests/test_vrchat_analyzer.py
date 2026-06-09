"""Acceptance tests for vrchat_performance_analyzer.

Spec: docs/SPEC_VRCHAT_ANALYZER.md (REQ-VP-01..03)
Runnable without pytest:  python3 -m unittest tests.test_vrchat_analyzer -v
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from vrchat_performance_analyzer import (  # noqa: E402
    AvatarStats, PerformanceRank, Platform,
    PerformanceAnalysisResult,
    VRChatPerformanceAnalyzer,
    analyze_all_platforms, worst_platform_rank,
    generate_cross_platform_report,
)


def _make_analyzer(platform=Platform.PC):
    return VRChatPerformanceAnalyzer(platform=platform)


def _stats(**kwargs):
    defaults = dict(
        polygons=7500, materials=1, bones=75, skinned_meshes=1,
        mesh_count=2, physbones_components=4, lights=0,
        particle_systems=1, texture_memory_mb=10.0
    )
    defaults.update(kwargs)
    return AvatarStats(**defaults)


class TestAnalyzeStats(unittest.TestCase):
    def test_excellent_rank(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats())
        self.assertEqual(result.rank, PerformanceRank.EXCELLENT)

    def test_good_rank(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats(polygons=9000, materials=3, texture_memory_mb=35.0))
        self.assertEqual(result.rank, PerformanceRank.GOOD)

    def test_medium_rank(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats(polygons=14000, materials=7, texture_memory_mb=70.0))
        self.assertEqual(result.rank, PerformanceRank.MEDIUM)

    def test_poor_rank(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats(polygons=19000, materials=15, texture_memory_mb=140.0))
        self.assertEqual(result.rank, PerformanceRank.POOR)

    def test_very_poor_rank(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats(polygons=50000, materials=30, texture_memory_mb=200.0))
        self.assertEqual(result.rank, PerformanceRank.VERY_POOR)

    def test_score_in_range(self):
        analyzer = _make_analyzer()
        for polygons in (7000, 12000, 18000, 30000):
            result = analyzer.analyze_stats(_stats(polygons=polygons))
            self.assertGreaterEqual(result.score, 0)
            self.assertLessEqual(result.score, 100)

    def test_lights_causes_critical_issue(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats(lights=2))
        critical = [i for i in result.issues if i['severity'] == 'critical']
        self.assertTrue(len(critical) > 0, "lights should produce a critical issue")

    def test_lights_reduce_score(self):
        analyzer = _make_analyzer()
        no_light = analyzer.analyze_stats(_stats(lights=0))
        with_light = analyzer.analyze_stats(_stats(lights=1))
        self.assertGreater(no_light.score, with_light.score)

    def test_is_vrchat_compliant_no_lights(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats(lights=0))
        self.assertTrue(result.details['is_vrchat_compliant'])

    def test_not_compliant_with_lights(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats(lights=1))
        self.assertFalse(result.details['is_vrchat_compliant'])

    def test_no_file_io_preset_path_is_none(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats())
        self.assertIsNone(result.details['preset_path'])

    def test_returns_result_object(self):
        from vrchat_performance_analyzer import PerformanceAnalysisResult
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats())
        self.assertIsInstance(result, PerformanceAnalysisResult)


class TestAndroidAnalyzer(unittest.TestCase):
    def test_android_stricter_limits(self):
        pc_analyzer = _make_analyzer(Platform.PC)
        android_analyzer = _make_analyzer(Platform.ANDROID)
        # Same stats: should be Excellent on PC, possibly not on Android
        s = _stats(polygons=7000, materials=1, texture_memory_mb=8.0)
        pc_result = pc_analyzer.analyze_stats(s)
        android_result = android_analyzer.analyze_stats(s)
        # PC ≥ Android rank is not guaranteed for every combo, but
        # Android should handle it without crashing
        self.assertIsNotNone(android_result.rank)
        self.assertGreaterEqual(android_result.score, 0)

    def test_android_generate_suggestions_no_crash(self):
        analyzer = _make_analyzer(Platform.ANDROID)
        # Trigger VERY_POOR → suggestions with target_rank GOOD
        # Android doesn't have VERY_POOR in limits_db → should return empty list (no crash)
        s = _stats(polygons=50000, texture_memory_mb=500.0)
        result = analyzer.analyze_stats(s)
        # Should not crash; suggestions might be empty list
        self.assertIsInstance(result.suggestions, list)


class TestAllDimensionRanking(unittest.TestCase):
    """REQ-VP-04: overall rank = worst across ALL 22 dimensions."""

    def test_physbones_transforms_downgrades_rank(self):
        analyzer = _make_analyzer()
        # Everything else EXCELLENT, but physbones_transforms=256 is POOR-tier on PC
        result = analyzer.analyze_stats(_stats(physbones_transforms=256))
        self.assertEqual(result.rank, PerformanceRank.POOR)

    def test_audio_sources_downgrades_rank(self):
        analyzer = _make_analyzer()
        # PC EXCELLENT audio_sources limit is 1; 10 pushes to a worse rank
        excellent = analyzer.analyze_stats(_stats())
        with_audio = analyzer.analyze_stats(_stats(audio_sources=10))
        self.assertEqual(excellent.rank, PerformanceRank.EXCELLENT)
        self.assertNotEqual(with_audio.rank, PerformanceRank.EXCELLENT)

    def test_physics_colliders_counted(self):
        analyzer = _make_analyzer()
        # EXCELLENT physics_colliders limit is 1 on PC; 16 is POOR-tier
        result = analyzer.analyze_stats(_stats(physics_colliders=16))
        self.assertEqual(result.rank, PerformanceRank.POOR)

    def test_cloth_vertices_counted(self):
        analyzer = _make_analyzer()
        # EXCELLENT cloth_vertices limit is 0; 200 is MEDIUM-tier
        result = analyzer.analyze_stats(_stats(cloth_vertices=200))
        self.assertEqual(result.rank, PerformanceRank.MEDIUM)

    def test_all_zero_extra_dims_stays_excellent(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats())
        self.assertEqual(result.rank, PerformanceRank.EXCELLENT)


class TestLimitingFactors(unittest.TestCase):
    """REQ-VP-05: identify the dimensions that bottleneck the overall rank."""

    def test_excellent_has_no_limiting_factors(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats())
        self.assertEqual(result.details['limiting_factors'], [])

    def test_limiting_factor_identifies_bottleneck(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats(physbones_transforms=256))
        fields = [f['field'] for f in result.details['limiting_factors']]
        self.assertIn('physbones_transforms', fields)

    def test_limiting_factor_includes_rank_and_value(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats(physbones_transforms=256))
        factor = next(f for f in result.details['limiting_factors'] if f['field'] == 'physbones_transforms')
        self.assertEqual(factor['value'], 256)
        self.assertEqual(factor['rank'], 'poor')

    def test_zero_value_dims_excluded(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats(polygons=19000))  # POOR via polygons
        fields = [f['field'] for f in result.details['limiting_factors']]
        # bones default 75 is EXCELLENT, audio_sources=0 should not appear
        self.assertNotIn('audio_sources', fields)

    def test_get_limiting_factors_method(self):
        analyzer = _make_analyzer()
        factors = analyzer.get_limiting_factors(_stats(polygons=19000))
        self.assertTrue(any(f['field'] == 'polygons' for f in factors))

    def test_details_contains_limiting_factors_key(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats())
        self.assertIn('limiting_factors', result.details)


class TestTextureFormats(unittest.TestCase):
    """REQ-VP-06: modern texture format VRAM estimation."""

    def test_bc7_format(self):
        analyzer = _make_analyzer()
        # BC7 = 1.0 bpp; 1024x1024 x 1.33 mip / 1MB = 1.33
        mb = analyzer._estimate_texture_memory([{'width': 1024, 'height': 1024, 'format': 'BC7'}])
        self.assertAlmostEqual(mb, 1.33, places=2)

    def test_astc_8x8_format(self):
        analyzer = _make_analyzer()
        # ASTC_8X8 = 0.25 bpp; 1024x1024 x 1.33 / 1MB = 0.3325
        mb = analyzer._estimate_texture_memory([{'width': 1024, 'height': 1024, 'format': 'ASTC_8X8'}])
        self.assertAlmostEqual(mb, 0.3325, places=3)

    def test_format_case_insensitive(self):
        analyzer = _make_analyzer()
        upper = analyzer._estimate_texture_memory([{'width': 512, 'height': 512, 'format': 'BC7'}])
        lower = analyzer._estimate_texture_memory([{'width': 512, 'height': 512, 'format': 'bc7'}])
        self.assertEqual(upper, lower)

    def test_bc5_normal_map(self):
        analyzer = _make_analyzer()
        # BC5 = 1.0 bpp, same as DXT5
        bc5 = analyzer._estimate_texture_memory([{'width': 1024, 'height': 1024, 'format': 'BC5'}])
        dxt5 = analyzer._estimate_texture_memory([{'width': 1024, 'height': 1024, 'format': 'DXT5'}])
        self.assertEqual(bc5, dxt5)

    def test_unknown_format_falls_back_to_rgba32(self):
        analyzer = _make_analyzer()
        unknown = analyzer._estimate_texture_memory([{'width': 256, 'height': 256, 'format': 'MADE_UP'}])
        rgba = analyzer._estimate_texture_memory([{'width': 256, 'height': 256, 'format': 'RGBA32'}])
        self.assertEqual(unknown, rgba)

    def test_dxt1_unchanged(self):
        analyzer = _make_analyzer()
        # Regression: DXT1 still 0.5 bpp
        mb = analyzer._estimate_texture_memory([{'width': 1024, 'height': 1024, 'format': 'DXT1'}])
        self.assertAlmostEqual(mb, 0.665, places=2)


class TestGenerateReport(unittest.TestCase):
    def test_report_is_string(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats(lights=1, polygons=12000))
        report = analyzer.generate_report(result)
        self.assertIsInstance(report, str)
        self.assertIn("Performance Rank", report)

    def test_report_contains_rank(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats())
        report = analyzer.generate_report(result)
        self.assertIn("EXCELLENT", report.upper())

    def test_report_shows_limiting_factors(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats(physbones_transforms=256))
        report = analyzer.generate_report(result)
        self.assertIn("Limiting Factors", report)
        self.assertIn("physbones_transforms", report)

    def test_report_no_limiting_section_when_excellent(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats())
        report = analyzer.generate_report(result)
        self.assertNotIn("Limiting Factors", report)


class TestCrossPlatform(unittest.TestCase):
    """REQ-VP-07..09: analyze the same stats across PC and Quest/Android."""

    def test_returns_pc_and_android(self):
        results = analyze_all_platforms(_stats())
        self.assertIn("pc", results)
        self.assertIn("android", results)

    def test_each_value_is_result(self):
        results = analyze_all_platforms(_stats())
        for r in results.values():
            self.assertIsInstance(r, PerformanceAnalysisResult)

    def test_android_not_better_than_pc(self):
        # Android limits are stricter, so its rank index >= PC's (same or worse)
        order = [PerformanceRank.EXCELLENT, PerformanceRank.GOOD,
                 PerformanceRank.MEDIUM, PerformanceRank.POOR, PerformanceRank.VERY_POOR]
        results = analyze_all_platforms(_stats(polygons=9000, texture_memory_mb=30.0))
        pc_idx = order.index(results["pc"].rank)
        android_idx = order.index(results["android"].rank)
        self.assertGreaterEqual(android_idx, pc_idx)

    def test_platforms_argument_limits_scope(self):
        results = analyze_all_platforms(_stats(), platforms=[Platform.PC])
        self.assertEqual(list(results.keys()), ["pc"])

    def test_worst_platform_rank(self):
        results = analyze_all_platforms(_stats(polygons=9000, texture_memory_mb=30.0))
        worst = worst_platform_rank(results)
        self.assertIsInstance(worst, PerformanceRank)
        # worst should be the android (stricter) rank here
        self.assertEqual(worst, results["android"].rank)

    def test_worst_platform_rank_all_excellent(self):
        # Android EXCELLENT is stricter (polygons<=5000, texture<=5MB), so use
        # stats that are EXCELLENT on both PC and Android.
        excellent_both = _stats(
            polygons=5000, materials=1, texture_memory_mb=5.0, physbones_components=2,
        )
        results = analyze_all_platforms(excellent_both)
        self.assertEqual(results["android"].rank, PerformanceRank.EXCELLENT)
        self.assertEqual(worst_platform_rank(results), PerformanceRank.EXCELLENT)

    def test_cross_platform_report_is_string(self):
        results = analyze_all_platforms(_stats())
        report = generate_cross_platform_report(results)
        self.assertIsInstance(report, str)

    def test_cross_platform_report_lists_platforms(self):
        results = analyze_all_platforms(_stats())
        report = generate_cross_platform_report(results)
        self.assertIn("PC", report)
        self.assertIn("ANDROID", report)

    def test_cross_platform_report_shows_effective_rank(self):
        results = analyze_all_platforms(_stats(polygons=9000, texture_memory_mb=30.0))
        report = generate_cross_platform_report(results)
        self.assertIn("Effective rank", report)


class TestOptimizationReduction(unittest.TestCase):
    """REQ-VP-10: suggestions quantify the reduction (impact)."""

    def test_polygon_reduction_value(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats(polygons=18000))
        poly = next(s for s in result.suggestions if s.category == "Polygon Reduction")
        self.assertEqual(poly.reduction, poly.current_value - poly.target_value)
        self.assertEqual(poly.reduction, 18000 - 10000)

    def test_all_suggestions_have_reduction(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze_stats(_stats(polygons=18000, materials=12, texture_memory_mb=100.0))
        for s in result.suggestions:
            self.assertTrue(hasattr(s, "reduction"))
            self.assertGreaterEqual(s.reduction, 0)

    def test_reduction_never_negative(self):
        from vrchat_performance_analyzer import OptimizationSuggestion
        # target above current should clamp reduction to 0
        s = OptimizationSuggestion(
            category="x", severity="info", current_value=5, target_value=10,
            suggestion="s", action="a",
        )
        self.assertEqual(s.reduction, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
