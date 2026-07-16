"""Tests for AvatarPerformanceMonitor — metrics, stats, health."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))
from avatar_performance_monitor import (
    AvatarPerformanceMetrics,
    AvatarPerformanceMonitor,
    PerformanceStats,
)


class TestAvatarPerformanceMetrics(unittest.TestCase):

    def test_basic_creation(self):
        from datetime import datetime, timezone
        m = AvatarPerformanceMetrics(
            operation_type="render",
            user_id="u1",
            start_time=datetime.now(timezone.utc),
            success=True,
        )
        self.assertEqual(m.operation_type, "render")
        self.assertEqual(m.user_id, "u1")

    def test_success_defaults_false(self):
        from datetime import datetime, timezone
        m = AvatarPerformanceMetrics(
            operation_type="render",
            user_id="u1",
            start_time=datetime.now(timezone.utc),
        )
        self.assertFalse(m.success)


class TestPerformanceStats(unittest.TestCase):

    def test_default_values(self):
        stats = PerformanceStats(operation_type="render")
        self.assertEqual(stats.total_operations, 0)
        self.assertEqual(stats.successful_operations, 0)

    def test_success_rate_zero_when_no_operations(self):
        stats = PerformanceStats(operation_type="render")
        self.assertEqual(stats.success_rate, 0.0)

    def test_success_rate_field(self):
        stats = PerformanceStats(operation_type="render", total_operations=10,
                                  successful_operations=8, success_rate=0.8)
        self.assertAlmostEqual(stats.success_rate, 0.8)


class TestAvatarPerformanceMonitorInit(unittest.TestCase):

    def setUp(self):
        self.monitor = AvatarPerformanceMonitor()

    def test_monitor_created(self):
        self.assertIsNotNone(self.monitor)

    def test_active_operations_starts_empty(self):
        self.assertEqual(len(self.monitor.active_operations), 0)

    def test_stats_cache_starts_empty(self):
        self.assertEqual(len(self.monitor.stats_cache), 0)


class TestAvatarPerformanceMonitorTracking(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        import tempfile
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmpfile.close()
        self.monitor = AvatarPerformanceMonitor()
        self.monitor.db_path = self.tmpfile.name
        await self.monitor._init_database()

    async def asyncTearDown(self):
        import contextlib
        import os
        with contextlib.suppress(OSError):
            os.unlink(self.tmpfile.name)

    async def test_start_operation_returns_id(self):
        op_id = await self.monitor.start_operation_tracking("render", "user1", "avatar1")
        self.assertIsNotNone(op_id)
        self.assertIsInstance(op_id, str)

    async def test_start_operation_adds_to_active(self):
        op_id = await self.monitor.start_operation_tracking("render", "user1", "avatar1")
        self.assertIn(op_id, self.monitor.active_operations)

    async def test_end_operation_removes_from_active(self):
        op_id = await self.monitor.start_operation_tracking("render", "user1", "avatar1")
        await self.monitor.end_operation_tracking(op_id, success=True)
        self.assertNotIn(op_id, self.monitor.active_operations)

    async def test_end_operation_active_count_zero(self):
        op_id = await self.monitor.start_operation_tracking("render", "user1", "avatar1")
        await self.monitor.end_operation_tracking(op_id, success=True)
        self.assertEqual(len(self.monitor.active_operations), 0)

    async def test_end_nonexistent_operation_no_error(self):
        await self.monitor.end_operation_tracking("nonexistent_op_id", success=True)
