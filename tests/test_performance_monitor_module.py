"""Tests for performance_monitor module."""
import sys
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestPerformanceMonitorBasic(unittest.TestCase):
    def _make(self):
        from performance_monitor import PerformanceMonitor
        return PerformanceMonitor()

    def test_init(self):
        pm = self._make()
        self.assertIsNotNone(pm)

    def test_validate_config(self):
        pm = self._make()
        issues = pm.validate_config()
        self.assertIsInstance(issues, dict)

    def test_get_system_info(self):
        pm = self._make()
        info = pm.get_system_info()
        self.assertIsNotNone(info)

    def test_check_thresholds(self):
        pm = self._make()
        result = pm.check_thresholds()
        self.assertIsInstance(result, dict)

    def test_not_running_initially(self):
        pm = self._make()
        self.assertFalse(getattr(pm, 'running', False))

    def test_add_alert_handler(self):
        pm = self._make()
        def handler(alerts): pass
        result = pm.add_alert_handler(handler)
        self.assertTrue(result)


class TestHybridSystemManager(unittest.TestCase):
    def test_init(self):
        from performance_monitor import HybridSystemManager
        mgr = HybridSystemManager()
        self.assertIsNotNone(mgr)

    def test_get_hybrid_system_manager_factory(self):
        from performance_monitor import get_hybrid_system_manager
        mgr = get_hybrid_system_manager()
        self.assertIsNotNone(mgr)

    def test_factory_is_callable(self):
        from performance_monitor import get_hybrid_system_manager
        import inspect
        # Could be async or sync
        self.assertTrue(callable(get_hybrid_system_manager))


if __name__ == '__main__':
    unittest.main()
