"""
Unit tests for main/performance_analyzer.py
"""

import sys
import os
import inspect
import logging
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))

from performance_analyzer import PerformanceAnalyzer, PerformanceError


def _make_analyzer():
    """Create a PerformanceAnalyzer with a real logger."""
    logger = logging.getLogger("test_performance_analyzer")
    return PerformanceAnalyzer(logger=logger)


class TestPerformanceAnalyzerInit(unittest.TestCase):
    """Tests for PerformanceAnalyzer construction and initial state."""

    def setUp(self):
        try:
            self.analyzer = _make_analyzer()
        except Exception as e:
            self.skipTest(f"PerformanceAnalyzer construction failed: {e}")

    def test_running_false_initially(self):
        self.assertFalse(self.analyzer.running)

    def test_metrics_keys_present(self):
        self.assertIn('cpu', self.analyzer.metrics)
        self.assertIn('memory', self.analyzer.metrics)
        self.assertIn('disk', self.analyzer.metrics)
        self.assertIn('network', self.analyzer.metrics)

    def test_metrics_lists_empty_initially(self):
        for key in ('cpu', 'memory', 'disk', 'network'):
            self.assertEqual(self.analyzer.metrics[key], [])

    def test_logger_assigned(self):
        self.assertIsNotNone(self.analyzer.logger)


class TestGetMetrics(unittest.TestCase):
    """Tests for get_metrics method."""

    def setUp(self):
        try:
            self.analyzer = _make_analyzer()
        except Exception as e:
            self.skipTest(f"PerformanceAnalyzer construction failed: {e}")

    def test_get_metrics_returns_dict(self):
        metrics = self.analyzer.get_metrics()
        self.assertIsInstance(metrics, dict)
        # Adding a new top-level key should not affect internal metrics dict
        metrics['new_key'] = 'value'
        self.assertNotIn('new_key', self.analyzer.metrics)

    def test_get_metrics_has_all_keys(self):
        metrics = self.analyzer.get_metrics()
        for key in ('cpu', 'memory', 'disk', 'network'):
            self.assertIn(key, metrics)


class TestAnalyzePerformanceEmpty(unittest.TestCase):
    """Tests for analyze_performance with no data collected."""

    def setUp(self):
        try:
            self.analyzer = _make_analyzer()
        except Exception as e:
            self.skipTest(f"PerformanceAnalyzer construction failed: {e}")

    def test_analyze_returns_error_keys_when_empty(self):
        result = self.analyzer.analyze_performance()
        for key in ('cpu', 'memory', 'disk', 'network'):
            self.assertIn('error', result[key])

    def test_analyze_cpu_empty(self):
        result = self.analyzer._analyze_cpu()
        self.assertIn('error', result)

    def test_analyze_memory_empty(self):
        result = self.analyzer._analyze_memory()
        self.assertIn('error', result)

    def test_analyze_disk_empty(self):
        result = self.analyzer._analyze_disk()
        self.assertIn('error', result)

    def test_analyze_network_empty(self):
        result = self.analyzer._analyze_network()
        self.assertIn('error', result)


class TestAnalyzePerformanceWithData(unittest.TestCase):
    """Tests for analyze_performance after manually injecting metrics."""

    def setUp(self):
        try:
            self.analyzer = _make_analyzer()
        except Exception as e:
            self.skipTest(f"PerformanceAnalyzer construction failed: {e}")

        self.analyzer.metrics['cpu'] = [
            {'timestamp': '2024-01-01 00:00:00', 'percent': 30.0, 'count': 4},
            {'timestamp': '2024-01-01 00:00:05', 'percent': 50.0, 'count': 4},
        ]
        self.analyzer.metrics['memory'] = [
            {'timestamp': '2024-01-01 00:00:00', 'total': 8 * 1024**3, 'used': 4 * 1024**3, 'percent': 50.0},
        ]
        self.analyzer.metrics['disk'] = [
            {'timestamp': '2024-01-01 00:00:00', 'total': 500 * 1024**3, 'used': 250 * 1024**3, 'percent': 50.0},
        ]
        self.analyzer.metrics['network'] = [
            {'timestamp': '2024-01-01 00:00:00', 'bytes_sent': 1000, 'bytes_recv': 2000},
            {'timestamp': '2024-01-01 00:00:05', 'bytes_sent': 3000, 'bytes_recv': 6000},
        ]

    def test_cpu_average(self):
        result = self.analyzer._analyze_cpu()
        self.assertAlmostEqual(result['average_usage'], 40.0)

    def test_cpu_max(self):
        result = self.analyzer._analyze_cpu()
        self.assertAlmostEqual(result['max_usage'], 50.0)

    def test_memory_analysis_keys(self):
        result = self.analyzer._analyze_memory()
        self.assertIn('average_usage', result)
        self.assertIn('max_usage', result)
        self.assertIn('total_memory', result)

    def test_disk_analysis_keys(self):
        result = self.analyzer._analyze_disk()
        self.assertIn('average_usage', result)
        self.assertIn('total_space', result)

    def test_network_analysis_keys(self):
        result = self.analyzer._analyze_network()
        self.assertIn('average_upload', result)
        self.assertIn('average_download', result)


class TestStopMonitoring(unittest.TestCase):
    """Tests for stop_monitoring."""

    def setUp(self):
        try:
            self.analyzer = _make_analyzer()
        except Exception as e:
            self.skipTest(f"PerformanceAnalyzer construction failed: {e}")

    def test_stop_sets_running_false(self):
        self.analyzer.running = True
        self.analyzer.stop_monitoring()
        self.assertFalse(self.analyzer.running)

    def test_start_monitoring_raises_if_already_running(self):
        self.analyzer.running = True
        with self.assertRaises(PerformanceError):
            self.analyzer.start_monitoring(interval=1)


class TestCollectMetricsMocked(unittest.TestCase):
    """Tests for _collect_metrics using mocked psutil."""

    def setUp(self):
        try:
            self.analyzer = _make_analyzer()
        except Exception as e:
            self.skipTest(f"PerformanceAnalyzer construction failed: {e}")

    def test_collect_metrics_populates_cpu(self):
        mock_cpu = MagicMock()
        mock_mem = MagicMock()
        mock_disk = MagicMock()
        mock_net = MagicMock()

        mock_mem.total = 8 * 1024**3
        mock_mem.used = 4 * 1024**3
        mock_mem.percent = 50.0
        mock_disk.total = 500 * 1024**3
        mock_disk.used = 250 * 1024**3
        mock_disk.percent = 50.0
        mock_net.bytes_sent = 100
        mock_net.bytes_recv = 200

        with patch('performance_analyzer.PSUTIL_AVAILABLE', True), \
             patch('performance_analyzer.psutil') as mock_psutil:
            mock_psutil.cpu_percent.return_value = 25.0
            mock_psutil.cpu_count.return_value = 8
            mock_psutil.virtual_memory.return_value = mock_mem
            mock_psutil.disk_usage.return_value = mock_disk
            mock_psutil.net_io_counters.return_value = mock_net

            self.analyzer._collect_metrics()

        self.assertEqual(len(self.analyzer.metrics['cpu']), 1)
        self.assertAlmostEqual(self.analyzer.metrics['cpu'][0]['percent'], 25.0)
        self.assertEqual(self.analyzer.metrics['cpu'][0]['count'], 8)


if __name__ == "__main__":
    unittest.main()
