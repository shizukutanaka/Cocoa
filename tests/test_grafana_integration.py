"""Acceptance tests for grafana_integration.py.

Spec: docs/SPEC_GRAFANA_INTEGRATION.md (REQ-GI-01)
Runnable without pytest:  python3 -m unittest tests.test_grafana_integration -v

GrafanaMetricsCollector / GrafanaDashboardManager / GrafanaIntegrationService
require `requests` (optional); EnhancedPerformanceMonitor has no grafana deps.
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

import grafana_integration as gi  # noqa: E402
from grafana_integration import (  # noqa: E402
    EnhancedPerformanceMonitor,
    get_enhanced_performance_monitor,
)


class TestEnhancedPerformanceMonitorInit(unittest.TestCase):
    def test_default_constructor_does_not_raise(self):
        pm = EnhancedPerformanceMonitor()
        self.assertIsNotNone(pm)

    def test_custom_config_applied(self):
        pm = EnhancedPerformanceMonitor({"interval": 2.0, "history_size": 50})
        self.assertEqual(pm.interval, 2.0)
        self.assertEqual(pm.history_size, 50)

    def test_grafana_disabled_by_default(self):
        pm = EnhancedPerformanceMonitor()
        self.assertFalse(pm.grafana_enabled)

    def test_grafana_service_none_by_default(self):
        pm = EnhancedPerformanceMonitor()
        self.assertIsNone(pm.grafana_service)

    def test_is_monitoring_false_by_default(self):
        pm = EnhancedPerformanceMonitor()
        self.assertFalse(pm.is_monitoring)

    def test_history_is_deque(self):
        from collections import deque
        pm = EnhancedPerformanceMonitor()
        self.assertIsInstance(pm.history, deque)

    def test_history_empty_on_init(self):
        pm = EnhancedPerformanceMonitor()
        self.assertEqual(len(pm.history), 0)


class TestGetPerformanceReport(unittest.TestCase):
    def test_empty_history_returns_dict(self):
        pm = EnhancedPerformanceMonitor()
        report = pm.get_performance_report()
        self.assertIsInstance(report, dict)

    def test_empty_history_returns_error_key(self):
        pm = EnhancedPerformanceMonitor()
        report = pm.get_performance_report()
        self.assertIn("error", report)

    def test_with_injected_metrics_returns_report(self):
        from datetime import datetime, timezone
        pm = EnhancedPerformanceMonitor()
        pm.history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": 30.0,
            "memory_percent": 50.0,
            "disk_io": 100.0,
            "network_io": 200.0,
        })
        report = pm.get_performance_report()
        self.assertIn("current", report)
        self.assertIn("statistics", report)

    def test_report_timestamp_is_utc(self):
        from datetime import datetime, timezone
        pm = EnhancedPerformanceMonitor()
        pm.history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": 20.0,
            "memory_percent": 40.0,
        })
        report = pm.get_performance_report()
        ts = report.get("timestamp", "")
        self.assertTrue(ts.endswith("+00:00"), f"Non-UTC timestamp: {ts!r}")

    def test_statistics_has_required_keys(self):
        from datetime import datetime, timezone
        pm = EnhancedPerformanceMonitor()
        pm.history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": 10.0,
            "memory_percent": 20.0,
        })
        report = pm.get_performance_report()
        stats = report.get("statistics", {})
        for key in ("cpu_avg", "memory_avg", "sample_count"):
            self.assertIn(key, stats)

    def test_grafana_enabled_false_in_report(self):
        from datetime import datetime, timezone
        pm = EnhancedPerformanceMonitor()
        pm.history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": 5.0,
        })
        report = pm.get_performance_report()
        self.assertFalse(report.get("grafana_enabled"))


class TestGetEnhancedPerformanceMonitor(unittest.TestCase):
    def setUp(self):
        gi._enhanced_monitor = None

    def test_returns_instance(self):
        pm = get_enhanced_performance_monitor()
        self.assertIsInstance(pm, EnhancedPerformanceMonitor)

    def test_singleton_same_instance(self):
        pm1 = get_enhanced_performance_monitor()
        pm2 = get_enhanced_performance_monitor()
        self.assertIs(pm1, pm2)

    def test_config_passed_through(self):
        pm = get_enhanced_performance_monitor({"interval": 3.0})
        self.assertEqual(pm.interval, 3.0)


class TestGrafanaAvailabilityFlag(unittest.TestCase):
    def test_grafana_available_is_bool(self):
        self.assertIsInstance(gi.GRAFANA_AVAILABLE, bool)

    def test_grafana_available_matches_requests_presence(self):
        import importlib.util
        requests_present = importlib.util.find_spec("requests") is not None
        self.assertEqual(gi.GRAFANA_AVAILABLE, requests_present)


if __name__ == "__main__":
    unittest.main(verbosity=2)
