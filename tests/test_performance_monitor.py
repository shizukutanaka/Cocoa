"""Acceptance tests for performance_monitor.py.

Spec: docs/SPEC_PERFORMANCE_MONITOR.md (REQ-PM-01..02)
Runnable without pytest:  python3 -m unittest tests.test_performance_monitor -v
"""
import asyncio
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from performance_monitor import PerformanceMonitor


class TestPerformanceMonitorCreation(unittest.TestCase):
    def test_default_constructor_does_not_raise(self):
        pm = PerformanceMonitor()
        self.assertIsNotNone(pm)

    def test_custom_config_applied(self):
        pm = PerformanceMonitor({"interval": 2.0, "history_size": 50})
        self.assertEqual(pm.interval, 2.0)
        self.assertEqual(pm.history_size, 50)

    def test_interval_minimum_is_05(self):
        pm = PerformanceMonitor({"interval": 0.01})
        self.assertEqual(pm.interval, 0.5)

    def test_history_size_minimum_is_1(self):
        pm = PerformanceMonitor({"history_size": 0})
        self.assertEqual(pm.history_size, 1)

    def test_running_is_false_by_default(self):
        pm = PerformanceMonitor()
        self.assertFalse(pm.running)

    def test_thresholds_initialized(self):
        pm = PerformanceMonitor()
        self.assertIn("memory", pm.thresholds)
        self.assertIn("cpu", pm.thresholds)


class TestUtcTimestamps(unittest.TestCase):
    """REQ-PM-01/02: timestamps must use UTC."""

    def test_get_performance_report_timestamp_is_utc(self):
        pm = PerformanceMonitor()
        report = pm.get_performance_report()
        ts = report.get("timestamp", "")
        self.assertTrue(ts.endswith("+00:00"), f"Non-UTC timestamp: {ts!r}")

    def test_add_custom_metric_timestamp_is_utc(self):
        pm = PerformanceMonitor()
        pm.add_custom_metric("fps", 60.0, "fps", "Frame rate")
        metrics = pm.get_custom_metrics()
        ts = metrics["fps"]["timestamp"]
        self.assertTrue(ts.endswith("+00:00"), f"Non-UTC custom metric timestamp: {ts!r}")

    def test_format_datetime_returns_string(self):
        pm = PerformanceMonitor()
        result = pm._format_datetime()
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


class TestValidateConfig(unittest.TestCase):
    def test_validate_config_returns_dict(self):
        pm = PerformanceMonitor()
        result = pm.validate_config()
        self.assertIsInstance(result, dict)

    def test_valid_config_has_no_issues(self):
        pm = PerformanceMonitor({"interval": 5.0, "history_size": 60})
        issues = pm.validate_config()
        self.assertEqual(issues, {})


class TestCustomMetrics(unittest.TestCase):
    def test_get_custom_metrics_returns_dict(self):
        pm = PerformanceMonitor()
        result = pm.get_custom_metrics()
        self.assertIsInstance(result, dict)

    def test_add_custom_metric_stored(self):
        pm = PerformanceMonitor()
        pm.add_custom_metric("latency", 25.3, "ms", "Network latency")
        metrics = pm.get_custom_metrics()
        self.assertIn("latency", metrics)
        self.assertEqual(metrics["latency"]["value"], 25.3)
        self.assertEqual(metrics["latency"]["unit"], "ms")

    def test_add_multiple_custom_metrics(self):
        pm = PerformanceMonitor()
        pm.add_custom_metric("a", 1.0)
        pm.add_custom_metric("b", 2.0)
        metrics = pm.get_custom_metrics()
        self.assertIn("a", metrics)
        self.assertIn("b", metrics)

    def test_overwrite_custom_metric(self):
        pm = PerformanceMonitor()
        pm.add_custom_metric("fps", 30.0)
        pm.add_custom_metric("fps", 60.0)
        metrics = pm.get_custom_metrics()
        self.assertEqual(metrics["fps"]["value"], 60.0)


class TestGetPerformanceReport(unittest.TestCase):
    def test_report_has_required_keys(self):
        pm = PerformanceMonitor()
        report = pm.get_performance_report()
        for key in ("timestamp", "custom_metrics", "error_stats", "consecutive_errors"):
            self.assertIn(key, report, f"Missing key: {key}")

    def test_report_custom_metrics_is_dict(self):
        pm = PerformanceMonitor()
        report = pm.get_performance_report()
        self.assertIsInstance(report["custom_metrics"], dict)


class TestCloudResourceInfo(unittest.TestCase):
    """CloudResourceInfo dataclass must include bandwidth_mbps field."""

    def test_cloud_resource_info_accepts_bandwidth_mbps(self):
        from performance_monitor import CloudResourceInfo
        resource = CloudResourceInfo(
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium",
            cost_per_hour=0.05,
            availability_score=0.99,
            latency_ms=55.0,
            bandwidth_mbps=100.0,
        )
        self.assertEqual(resource.bandwidth_mbps, 100.0)

    def test_cloud_resource_info_bandwidth_default(self):
        from performance_monitor import CloudResourceInfo
        resource = CloudResourceInfo(
            provider="gcp",
            region="us-central1",
            instance_type="n1-standard-1",
            cost_per_hour=0.04,
            availability_score=0.99,
            latency_ms=60.0,
        )
        self.assertEqual(resource.bandwidth_mbps, 100.0)


class TestHybridSystemManagerInitialize(unittest.TestCase):
    """HybridSystemManager.initialize() must return promptly.

    Two bugs were present:
    1. CloudResourceInfo lacked bandwidth_mbps → TypeError on construction.
    2. initialize() used `await self._start_energy_monitoring()` which is an
       infinite while-True loop → initialize() never returned.
    """

    def test_initialize_does_not_block(self):
        from performance_monitor import HybridSystemManager
        mgr = HybridSystemManager()

        async def run():
            await asyncio.wait_for(mgr.initialize(), timeout=5.0)

        asyncio.run(run())

    def test_initialize_populates_cloud_resources(self):
        from performance_monitor import HybridSystemManager
        mgr = HybridSystemManager()
        asyncio.run(mgr.initialize())
        self.assertGreater(len(mgr.cloud_resources), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
