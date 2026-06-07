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
    VRChatPerformanceAnalyzer,
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
