"""Acceptance tests for global_edge_manager.py.

Spec: docs/SPEC_GLOBAL_EDGE_MANAGER.md (REQ-GEM-01)
Runnable without pytest:  python3 -m unittest tests.test_global_edge_manager -v
"""
import os
import sys
import tempfile
import unittest
from datetime import timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from global_edge_manager import (
    EdgeNode,
    GlobalEdgeManager,
    TrafficRoute,
)


def _make_manager(tmpdir):
    return GlobalEdgeManager(edge_dir=str(Path(tmpdir) / "edge"))


class TestGlobalEdgeManagerInit(unittest.TestCase):
    def test_constructor_does_not_raise(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            self.assertIsNotNone(mgr)

    def test_edge_nodes_initialized_as_dict(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            self.assertIsInstance(mgr.edge_nodes, dict)

    def test_content_cache_initialized_as_dict(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            self.assertIsInstance(mgr.content_cache, dict)

    def test_traffic_routes_initialized_as_dict(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            self.assertIsInstance(mgr.traffic_routes, dict)

    def test_regions_initialized(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            self.assertIn("north_america", mgr.regions)
            self.assertIn("europe", mgr.regions)

    def test_cdn_domains_empty_by_default(self):
        # This project does not own/operate any cdn.*/edge.*/global.* domain
        # -- cdn_domains must not silently default to a fictional, unowned
        # one. Empty (unconfigured) is the honest default.
        saved = os.environ.pop("COCOA_CDN_DOMAINS", None)
        try:
            with tempfile.TemporaryDirectory() as td:
                mgr = _make_manager(td)
                self.assertEqual(mgr.cdn_domains, [])
        finally:
            if saved is not None:
                os.environ["COCOA_CDN_DOMAINS"] = saved

    def test_cdn_domains_populated_from_env_var(self):
        saved = os.environ.get("COCOA_CDN_DOMAINS")
        os.environ["COCOA_CDN_DOMAINS"] = "cdn.example.org, edge.example.org"
        try:
            with tempfile.TemporaryDirectory() as td:
                mgr = _make_manager(td)
                self.assertEqual(mgr.cdn_domains, ["cdn.example.org", "edge.example.org"])
        finally:
            if saved is None:
                os.environ.pop("COCOA_CDN_DOMAINS", None)
            else:
                os.environ["COCOA_CDN_DOMAINS"] = saved


class TestGetGlobalEdgeStatus(unittest.TestCase):
    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            status = mgr.get_global_edge_status()
            self.assertIsInstance(status, dict)

    def test_has_required_keys(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            status = mgr.get_global_edge_status()
            for key in ("total_nodes", "active_nodes", "total_cache_entries",
                        "total_routes", "cache_hit_rate", "average_latency_ms"):
                self.assertIn(key, status)

    def test_total_nodes_zero_on_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            status = mgr.get_global_edge_status()
            self.assertEqual(status["total_nodes"], 0)

    def test_regions_in_status(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            status = mgr.get_global_edge_status()
            self.assertIn("regions", status)
            self.assertIsInstance(status["regions"], dict)


class TestEdgeNodeManualRegistration(unittest.TestCase):
    def _make_node(self, node_id="node-1"):
        from datetime import datetime, timezone
        return EdgeNode(
            node_id=node_id,
            region="us-east-1",
            country="US",
            city="New York",
            coordinates=(40.7128, -74.0060),
            ip_address="1.2.3.4",
            capacity={"cpu": 8, "memory": 16384, "storage": 512000},
            current_load={"cpu": 0.2, "memory": 0.3, "storage": 0.1},
            latency_ms=50.0,
            bandwidth_mbps=1000.0,
            status="active",
            services=["avatar", "model"],
            last_health_check=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )

    def test_edge_node_registers_correctly(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            node = self._make_node("n1")
            mgr.edge_nodes["n1"] = node
            self.assertIn("n1", mgr.edge_nodes)

    def test_registered_node_retrievable(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            node = self._make_node("n2")
            mgr.edge_nodes["n2"] = node
            self.assertEqual(mgr.edge_nodes["n2"].node_id, "n2")

    def test_registered_node_health_check_is_utc(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            node = self._make_node("n3")
            mgr.edge_nodes["n3"] = node
            hc = mgr.edge_nodes["n3"].last_health_check
            self.assertIsNotNone(hc.tzinfo)
            self.assertEqual(hc.tzinfo, timezone.utc)

    def test_status_reflects_registered_node(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            node = self._make_node("n4")
            mgr.edge_nodes["n4"] = node
            status = mgr.get_global_edge_status()
            self.assertEqual(status["total_nodes"], 1)
            self.assertEqual(status["active_nodes"], 1)

    def test_get_nonexistent_node_is_none(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            result = mgr.edge_nodes.get("does_not_exist")
            self.assertIsNone(result)


class TestDataclassConstruction(unittest.TestCase):
    def test_edge_node_created_with_utc_timestamps(self):
        from datetime import datetime, timezone
        node = EdgeNode(
            node_id="x",
            region="eu-west-1",
            country="IE",
            city="Dublin",
            coordinates=(53.33, -6.25),
            ip_address="10.0.0.1",
            capacity={},
            current_load={},
            latency_ms=30.0,
            bandwidth_mbps=500.0,
            status="active",
            services=[],
            last_health_check=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        self.assertIsNotNone(node.last_health_check.tzinfo)

    def test_traffic_route_construction(self):
        from datetime import datetime, timezone
        route = TrafficRoute(
            route_id="r1",
            source_region="us-east-1",
            destination_region="eu-west-1",
            optimal_nodes=["n1", "n2"],
            estimated_latency_ms=80.0,
            bandwidth_capacity_mbps=500.0,
            cost_per_gb=0.05,
            reliability_score=0.99,
            created_at=datetime.now(timezone.utc),
        )
        self.assertEqual(route.route_id, "r1")
        self.assertIsNotNone(route.created_at.tzinfo)


class TestGlobalEdgeManagerInitializeDoesNotBlock(unittest.IsolatedAsyncioTestCase):
    """GlobalEdgeManager.initialize() must return promptly.

    Bug: initialize() called `await self._start_health_monitoring()` and
    `await self._start_analytics_collection()`, both of which are `while True:`
    infinite loops. The health monitoring blocked initialize() forever, and the
    analytics collection was never reached.
    Fix: use asyncio.create_task() so both loops run in the background.
    """

    async def test_initialize_completes_without_blocking(self):
        import asyncio
        from unittest.mock import AsyncMock, patch

        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            with patch.object(mgr, '_initialize_edge_nodes', new=AsyncMock()), \
                 patch.object(mgr, '_load_traffic_routes', new=AsyncMock()):
                try:
                    await asyncio.wait_for(mgr.initialize(), timeout=2.0)
                except asyncio.TimeoutError:
                    self.fail("GlobalEdgeManager.initialize() blocked — "
                              "background loops must be create_task'd, not awaited")

    async def test_initialize_launches_two_background_tasks(self):
        """initialize() should launch health monitoring AND analytics as tasks."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(td)
            tasks_before = len(asyncio.all_tasks())
            with patch.object(mgr, '_initialize_edge_nodes', new=AsyncMock()), \
                 patch.object(mgr, '_load_traffic_routes', new=AsyncMock()):
                await asyncio.wait_for(mgr.initialize(), timeout=2.0)
            tasks_after = len(asyncio.all_tasks())
            self.assertGreaterEqual(tasks_after - tasks_before, 2,
                                    "Both _start_health_monitoring and _start_analytics_collection "
                                    "should be created as background tasks")


if __name__ == "__main__":
    unittest.main(verbosity=2)
