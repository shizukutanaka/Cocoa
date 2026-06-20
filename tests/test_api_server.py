"""Tests for main/api_server.py — models and ConnectionManager."""
import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "main"))

import api_server
from api_server import (
    FASTAPI_AVAILABLE,
    BackupInfo,
    ConnectionManager,
    HealthCheck,
    SecurityReport,
    SystemMetrics,
)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestPydanticModels(unittest.TestCase):

    def test_health_check_instantiation(self):
        hc = HealthCheck(
            status="healthy",
            timestamp="2024-01-01T00:00:00Z",
            version="2.0.0",
        )
        self.assertEqual(hc.status, "healthy")
        self.assertEqual(hc.version, "2.0.0")
        self.assertIsNone(hc.uptime)

    def test_health_check_with_uptime(self):
        hc = HealthCheck(
            status="healthy",
            timestamp="2024-01-01T00:00:00Z",
            version="2.0.0",
            uptime=3600.0,
        )
        self.assertEqual(hc.uptime, 3600.0)

    def test_system_metrics_instantiation(self):
        sm = SystemMetrics(
            cpu=25.0,
            memory=60.0,
            disk_io=5.0,
            network_io=2.0,
            process_memory=128.0,
            timestamp="2024-01-01T00:00:00Z",
        )
        self.assertEqual(sm.cpu, 25.0)
        self.assertEqual(sm.memory, 60.0)

    def test_backup_info_instantiation(self):
        bi = BackupInfo(
            backup_id="bk-001",
            timestamp="2024-01-01T00:00:00Z",
            size_bytes=1024,
            status="completed",
            verified=True,
        )
        self.assertTrue(bi.verified)
        self.assertEqual(bi.size_bytes, 1024)

    def test_security_report_instantiation(self):
        sr = SecurityReport(
            threat_level="low",
            total_events_24h=5,
            active_lockouts=0,
            suspicious_activities=1,
            last_scan="2024-01-01T00:00:00Z",
        )
        self.assertEqual(sr.threat_level, "low")
        self.assertEqual(sr.total_events_24h, 5)


class TestConnectionManager(unittest.TestCase):

    def setUp(self):
        self.manager = ConnectionManager()

    def test_starts_with_no_connections(self):
        self.assertEqual(len(self.manager.active_connections), 0)

    def test_disconnect_removes_connection(self):
        mock_ws = MagicMock()
        self.manager.active_connections.append(mock_ws)
        self.manager.disconnect(mock_ws)
        self.assertNotIn(mock_ws, self.manager.active_connections)

    def test_disconnect_unknown_connection_is_noop(self):
        mock_ws = MagicMock()
        self.manager.disconnect(mock_ws)  # Should not raise
        self.assertEqual(len(self.manager.active_connections), 0)

    def test_connect_adds_to_active_connections(self):
        mock_ws = AsyncMock()
        asyncio.run(self.manager.connect(mock_ws))
        self.assertIn(mock_ws, self.manager.active_connections)

    def test_connect_calls_accept(self):
        mock_ws = AsyncMock()
        asyncio.run(self.manager.connect(mock_ws))
        mock_ws.accept.assert_called_once()

    def test_broadcast_sends_to_all(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        self.manager.active_connections = [ws1, ws2]
        asyncio.run(self.manager.broadcast("hello"))
        ws1.send_text.assert_called_once_with("hello")
        ws2.send_text.assert_called_once_with("hello")

    def test_broadcast_removes_failed_connections(self):
        ws_good = AsyncMock()
        ws_bad = AsyncMock()
        ws_bad.send_text.side_effect = RuntimeError("disconnected")
        self.manager.active_connections = [ws_good, ws_bad]
        asyncio.run(self.manager.broadcast("msg"))
        self.assertNotIn(ws_bad, self.manager.active_connections)
        self.assertIn(ws_good, self.manager.active_connections)

    def test_broadcast_tolerates_concurrent_disconnect(self):
        """broadcast must snapshot active_connections so a disconnect mid-send doesn't crash.

        Bug: iterating self.active_connections directly while await send_text() yields
        allows a concurrent disconnect() to remove an item, raising RuntimeError.
        Fix: iterate list(self.active_connections) — a snapshot taken before the loop.
        """
        manager = self.manager

        async def send_that_disconnects(msg):
            # Simulate another connection being removed while we are mid-broadcast
            if manager.active_connections:
                manager.active_connections.pop()

        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws1.send_text = send_that_disconnects
        manager.active_connections = [ws1, ws2]
        # Must not raise RuntimeError: list changed size during iteration
        asyncio.run(manager.broadcast("test"))


class TestModuleConstants(unittest.TestCase):

    def test_fastapi_available_is_bool(self):
        self.assertIsInstance(FASTAPI_AVAILABLE, bool)

    def test_manager_singleton_exists(self):
        self.assertIsInstance(api_server.manager, ConnectionManager)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestBulkListingActionRequest(unittest.TestCase):
    """Unit-test the BulkListingActionRequest Pydantic model."""

    def test_valid_unpublish(self):
        from api_server import BulkListingActionRequest
        req = BulkListingActionRequest(listing_ids=["id1", "id2"], action="unpublish")
        self.assertEqual(req.action, "unpublish")
        self.assertEqual(req.listing_ids, ["id1", "id2"])

    def test_valid_delete(self):
        from api_server import BulkListingActionRequest
        req = BulkListingActionRequest(listing_ids=["id1"], action="delete")
        self.assertEqual(req.action, "delete")

    def test_empty_listing_ids_allowed_at_model_level(self):
        from api_server import BulkListingActionRequest
        # Validation of empty list happens at handler level, not model level
        req = BulkListingActionRequest(listing_ids=[], action="unpublish")
        self.assertEqual(req.listing_ids, [])


class TestBulkLogicDirect(unittest.TestCase):
    """Test bulk admin logic directly via MarketplaceStore without HTTP layer."""

    def setUp(self):
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "main"))
        from avatar_marketplace import MarketplaceStore
        self.mp = MarketplaceStore()
        self.l1 = self.mp.publish(
            avatar_id="av1", owner_id="u1", owner_username="alice",
            name="Avatar 1", description="d", tags=[], category="vrc", parameters={},
        )
        self.l2 = self.mp.publish(
            avatar_id="av2", owner_id="u2", owner_username="bob",
            name="Avatar 2", description="d", tags=[], category="vrc", parameters={},
        )

    def test_direct_unpublish_via_lock(self):
        with self.mp._lock:
            self.l1.is_active = False
        listing = self.mp.get_listing(self.l1.listing_id)
        self.assertFalse(listing.is_active)

    def test_direct_delete_via_lock(self):
        lid = self.l2.listing_id
        with self.mp._lock:
            self.mp._listings.pop(lid, None)
        self.assertIsNone(self.mp.get_listing(lid))

    def test_delete_nonexistent_is_noop(self):
        with self.mp._lock:
            self.mp._listings.pop("no-such-id", None)
        # Still has original listings
        self.assertIsNotNone(self.mp.get_listing(self.l1.listing_id))


class TestLegacyApiSecret(unittest.TestCase):
    """The legacy API-secret fallback must fail closed when unconfigured."""

    def setUp(self):
        self._saved = os.environ.get("API_SECRET_TOKEN")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("API_SECRET_TOKEN", None)
        else:
            os.environ["API_SECRET_TOKEN"] = self._saved

    def test_unset_env_denies_everything(self):
        os.environ.pop("API_SECRET_TOKEN", None)
        # The old hardcoded default must no longer be accepted.
        self.assertFalse(api_server._verify_legacy_api_secret("default-secret"))
        self.assertFalse(api_server._verify_legacy_api_secret(""))
        self.assertFalse(api_server._verify_legacy_api_secret("anything"))

    def test_empty_env_denies_everything(self):
        os.environ["API_SECRET_TOKEN"] = ""
        self.assertFalse(api_server._verify_legacy_api_secret("default-secret"))
        self.assertFalse(api_server._verify_legacy_api_secret(""))

    def test_configured_secret_matches_only_exact(self):
        os.environ["API_SECRET_TOKEN"] = "s3kr3t-configured"
        self.assertTrue(api_server._verify_legacy_api_secret("s3kr3t-configured"))
        self.assertFalse(api_server._verify_legacy_api_secret("default-secret"))
        self.assertFalse(api_server._verify_legacy_api_secret("wrong"))


if __name__ == "__main__":
    unittest.main()
