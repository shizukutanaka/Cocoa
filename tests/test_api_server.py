"""Tests for main/api_server.py — models and ConnectionManager."""
import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

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


class TestCloneListingSearchAndNotify(unittest.TestCase):
    """clone_listing endpoint must register in SearchIndex and fire saved-search
    notifications — identical to what publish_listing does — so cloned avatars
    are immediately discoverable and watchers are alerted."""

    def _fake_cloned(self):
        listing = MagicMock()
        listing.listing_id = "cloned-lid"
        listing.owner_id = "u2"
        listing.name = "Cool Clone"
        listing.description = "cloned avatar"
        listing.tags = ["vrc"]
        listing.category = "vrc"
        listing.platform = "vrchat"
        listing.parameters = {}
        listing.is_active = True
        listing.to_dict.return_value = {"listing_id": "cloned-lid"}
        return listing

    def test_clone_registers_in_search_index(self):
        fake = self._fake_cloned()
        mock_mp = MagicMock()
        mock_mp.clone_listing.return_value = fake
        mock_idx = MagicMock()

        with patch.object(api_server, "get_marketplace", lambda: mock_mp), \
             patch.object(api_server, "get_search_index", lambda: mock_idx), \
             patch.object(api_server, "get_saved_search_store", None), \
             patch.object(api_server, "get_notification_queue", None):
            asyncio.run(api_server.clone_listing(
                "src-lid", {"user_id": "u2", "username": "bob"}
            ))

        mock_idx.index_from_dict.assert_called_once()
        doc = mock_idx.index_from_dict.call_args[0][0]
        self.assertEqual(doc["doc_id"], "cloned-lid")
        self.assertEqual(doc["platform"], "vrchat")
        self.assertTrue(doc["is_public"])

    def test_clone_sends_saved_search_notification(self):
        fake = self._fake_cloned()
        mock_mp = MagicMock()
        mock_mp.clone_listing.return_value = fake

        ss = MagicMock()
        ss.search_id = "ss-1"
        ss.user_id = "u3"
        ss.name = "VRC Search"
        mock_store = MagicMock()
        mock_store.find_matches.return_value = [ss]
        mock_queue = MagicMock()

        with patch.object(api_server, "get_marketplace", lambda: mock_mp), \
             patch.object(api_server, "get_search_index", None), \
             patch.object(api_server, "get_saved_search_store", lambda: mock_store), \
             patch.object(api_server, "get_notification_queue", lambda: mock_queue):
            asyncio.run(api_server.clone_listing(
                "src-lid", {"user_id": "u2", "username": "bob"}
            ))

        mock_store.find_matches.assert_called_once_with(fake)
        mock_queue.push.assert_called_once()
        args = mock_queue.push.call_args[0]
        self.assertEqual(args[0], "u3")
        self.assertEqual(args[1], "saved_search_match")

    def test_clone_does_not_notify_the_cloner(self):
        """The cloner must be excluded from saved-search notifications even if
        they have a matching saved search, consistent with publish_listing."""
        fake = self._fake_cloned()
        mock_mp = MagicMock()
        mock_mp.clone_listing.return_value = fake

        ss = MagicMock()
        ss.search_id = "ss-2"
        ss.user_id = "u2"   # same as cloner
        ss.name = "My Search"
        mock_store = MagicMock()
        mock_store.find_matches.return_value = [ss]
        mock_queue = MagicMock()

        with patch.object(api_server, "get_marketplace", lambda: mock_mp), \
             patch.object(api_server, "get_search_index", None), \
             patch.object(api_server, "get_saved_search_store", lambda: mock_store), \
             patch.object(api_server, "get_notification_queue", lambda: mock_queue):
            asyncio.run(api_server.clone_listing(
                "src-lid", {"user_id": "u2", "username": "bob"}
            ))

        mock_queue.push.assert_not_called()

    def test_clone_no_duplicate_notifications_for_same_user(self):
        """A user with two matching saved searches gets only one notification."""
        fake = self._fake_cloned()
        mock_mp = MagicMock()
        mock_mp.clone_listing.return_value = fake

        ss1 = MagicMock()
        ss1.search_id = "ss-a"
        ss1.user_id = "u3"
        ss1.name = "Search A"
        ss2 = MagicMock()
        ss2.search_id = "ss-b"
        ss2.user_id = "u3"
        ss2.name = "Search B"
        mock_store = MagicMock()
        mock_store.find_matches.return_value = [ss1, ss2]
        mock_queue = MagicMock()

        with patch.object(api_server, "get_marketplace", lambda: mock_mp), \
             patch.object(api_server, "get_search_index", None), \
             patch.object(api_server, "get_saved_search_store", lambda: mock_store), \
             patch.object(api_server, "get_notification_queue", lambda: mock_queue):
            asyncio.run(api_server.clone_listing(
                "src-lid", {"user_id": "u2", "username": "bob"}
            ))

        self.assertEqual(mock_queue.push.call_count, 1)


class TestPublishVersionSearchIndex(unittest.TestCase):
    """publish_listing_version must re-index the SearchIndex when name or
    description change, because publish_version() updates those fields on the
    live listing object in place — leaving the index stale otherwise."""

    def _fake_listing(self):
        lst = MagicMock()
        lst.listing_id = "lst-1"
        lst.owner_id = "u1"
        lst.name = "Updated Name"
        lst.description = "new desc"
        lst.tags = ["vrc"]
        lst.category = "vrc"
        lst.platform = "vrchat"
        lst.parameters = {}
        lst.is_active = True
        return lst

    def test_version_with_new_name_reindexes(self):
        fake_listing = self._fake_listing()
        fake_version = MagicMock()
        fake_version.to_dict.return_value = {"version_id": "v1"}
        mock_mp = MagicMock()
        mock_mp.publish_version.return_value = fake_version
        mock_mp.get_listing.return_value = fake_listing
        mock_idx = MagicMock()

        body = MagicMock()
        body.changelog = "new version"
        body.name = "Updated Name"
        body.description = None
        body.parameters = None

        with patch.object(api_server, "get_marketplace", lambda: mock_mp), \
             patch.object(api_server, "get_search_index", lambda: mock_idx):
            asyncio.run(api_server.publish_listing_version(
                "lst-1", body, {"user_id": "u1"}
            ))

        mock_idx.index_from_dict.assert_called_once()
        doc = mock_idx.index_from_dict.call_args[0][0]
        self.assertEqual(doc["doc_id"], "lst-1")
        self.assertEqual(doc["name"], "Updated Name")

    def test_version_with_new_description_reindexes(self):
        fake_listing = self._fake_listing()
        fake_version = MagicMock()
        fake_version.to_dict.return_value = {}
        mock_mp = MagicMock()
        mock_mp.publish_version.return_value = fake_version
        mock_mp.get_listing.return_value = fake_listing
        mock_idx = MagicMock()

        body = MagicMock()
        body.changelog = "desc update"
        body.name = None
        body.description = "new desc"
        body.parameters = None

        with patch.object(api_server, "get_marketplace", lambda: mock_mp), \
             patch.object(api_server, "get_search_index", lambda: mock_idx):
            asyncio.run(api_server.publish_listing_version(
                "lst-1", body, {"user_id": "u1"}
            ))

        mock_idx.index_from_dict.assert_called_once()

    def test_version_changelog_only_skips_reindex(self):
        """When only changelog is provided (name and description both None),
        no re-index is needed — the indexed text hasn't changed."""
        fake_version = MagicMock()
        fake_version.to_dict.return_value = {}
        mock_mp = MagicMock()
        mock_mp.publish_version.return_value = fake_version
        mock_idx = MagicMock()

        body = MagicMock()
        body.changelog = "bug fix"
        body.name = None
        body.description = None
        body.parameters = None

        with patch.object(api_server, "get_marketplace", lambda: mock_mp), \
             patch.object(api_server, "get_search_index", lambda: mock_idx):
            asyncio.run(api_server.publish_listing_version(
                "lst-1", body, {"user_id": "u1"}
            ))

        mock_idx.index_from_dict.assert_not_called()


if __name__ == "__main__":
    unittest.main()
