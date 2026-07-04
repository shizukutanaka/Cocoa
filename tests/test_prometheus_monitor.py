"""Tests for prometheus_monitor module."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestEnvironmentEnum(unittest.TestCase):
    def test_values(self):
        from prometheus_monitor import Environment
        self.assertIn("prod", [e.value for e in Environment])
        self.assertIn("dev", [e.value for e in Environment])


class TestMetricConfig(unittest.TestCase):
    def test_defaults(self):
        from prometheus_monitor import MetricConfig
        mc = MetricConfig()
        self.assertEqual(mc.job_name, "cocoa")
        self.assertIsInstance(mc.scrape_interval, int)


class TestEnhancedPrometheusMonitor(unittest.TestCase):
    def _make_monitor(self):
        from prometheus_monitor import (
            PROMETHEUS_AVAILABLE,
            EnhancedPrometheusMonitor,
            Environment,
        )
        if not PROMETHEUS_AVAILABLE:
            self.skipTest("prometheus_client not installed")
        return EnhancedPrometheusMonitor(environment=Environment.DEV)

    def test_init(self):
        mon = self._make_monitor()
        self.assertIsNotNone(mon)

    def test_has_record_request(self):
        from prometheus_monitor import EnhancedPrometheusMonitor
        self.assertTrue(hasattr(EnhancedPrometheusMonitor, 'record_request'))

    def test_has_record_operation(self):
        from prometheus_monitor import EnhancedPrometheusMonitor
        self.assertTrue(hasattr(EnhancedPrometheusMonitor, 'record_operation'))


class TestMetricsServer(unittest.TestCase):
    def test_init(self):
        from prometheus_monitor import (
            PROMETHEUS_AVAILABLE,
            EnhancedPrometheusMonitor,
            Environment,
            MetricsServer,
        )
        if not PROMETHEUS_AVAILABLE:
            self.skipTest("prometheus_client not installed")
        mon = EnhancedPrometheusMonitor(environment=Environment.DEV)
        srv = MetricsServer(monitor=mon, port=9999)
        self.assertEqual(srv.port, 9999)


class TestGetPrometheusMonitor(unittest.TestCase):
    def test_returns_singleton(self):
        from prometheus_monitor import PROMETHEUS_AVAILABLE, get_prometheus_monitor
        if not PROMETHEUS_AVAILABLE:
            self.skipTest("prometheus_client not installed")
        m1 = get_prometheus_monitor()
        m2 = get_prometheus_monitor()
        self.assertIs(m1, m2)

    def test_returns_enhanced_prometheus_monitor_instance(self):
        from prometheus_monitor import (
            PROMETHEUS_AVAILABLE,
            EnhancedPrometheusMonitor,
            get_prometheus_monitor,
        )
        if not PROMETHEUS_AVAILABLE:
            self.skipTest("prometheus_client not installed")
        self.assertIsInstance(get_prometheus_monitor(), EnhancedPrometheusMonitor)


if __name__ == '__main__':
    unittest.main()
