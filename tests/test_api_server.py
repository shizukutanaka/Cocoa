"""Tests for main/api_server.py — models and ConnectionManager."""
import asyncio
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "main"))

import api_server
from api_server import (
    FASTAPI_AVAILABLE,
    BackupInfo,
    ConnectionManager,
    HealthCheck,
    HTTPException,
    SecurityReport,
    SystemMetrics,
)
from auth_manager import AuthError, PendingTwoFactor, TokenPair


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


class TestCheckoutReferralExceptionIsolation(unittest.TestCase):
    """on_first_purchase() in checkout_cart / purchase_bundle must be wrapped
    in try/except so an unexpected exception from the referral layer cannot
    crash a checkout that already debited the buyer's credits (post-payment 500
    would require support intervention to determine whether the order went through)."""

    def _make_checkout_result(self, total: int = 100):
        return {
            "success": True,
            "order": {
                "order_id": "ord-1",
                "total_credits": total,
                "items": [],
            },
            "failed_items": [],
        }

    def test_checkout_cart_survives_referral_exception(self):
        mock_cm = MagicMock()
        mock_cm.checkout.return_value = self._make_checkout_result(total=100)

        exploding_rm = MagicMock()
        exploding_rm.on_first_purchase.side_effect = RuntimeError("referral db exploded")

        with patch.object(api_server, "get_cart_manager", lambda: mock_cm), \
             patch.object(api_server, "get_marketplace", MagicMock()), \
             patch.object(api_server, "get_referral_manager", lambda: exploding_rm), \
             patch.object(api_server, "get_membership_manager", None), \
             patch.object(api_server, "get_notification_queue", None):
            result = asyncio.run(api_server.checkout_cart({"user_id": "u1", "username": "alice"}))

        # checkout must succeed despite the referral exception
        self.assertTrue(result.get("success"))

    def test_purchase_bundle_survives_referral_exception(self):
        mock_bm = MagicMock()
        mock_bm.purchase_bundle.return_value = {
            "purchased": [{"listing_id": "lid1", "owner_id": "creator1"}],
            "total_charged": 200,
            "failed": [],
        }

        exploding_rm = MagicMock()
        exploding_rm.on_first_purchase.side_effect = RuntimeError("referral db exploded")

        with patch.object(api_server, "get_bundle_manager", lambda: mock_bm), \
             patch.object(api_server, "get_marketplace", MagicMock()), \
             patch.object(api_server, "get_referral_manager", lambda: exploding_rm), \
             patch.object(api_server, "get_membership_manager", None), \
             patch.object(api_server, "get_notification_queue", None):
            result = asyncio.run(api_server.purchase_bundle(
                "bundle-1", {"user_id": "u1", "username": "alice"}
            ))

        # purchase must succeed despite the referral exception
        self.assertIn("purchased", result)


class TestBundleActivateDeactivateEndpoints(unittest.TestCase):
    """POST /api/bundles/{id}/activate and /deactivate. BundleManager.activate_bundle()/
    deactivate_bundle() were fully implemented and unit-tested at the store layer, but
    no HTTP endpoint ever called them -- a creator had no way to pause a bundle short
    of permanently deleting it, and list_my_bundles' include_inactive flag had nothing
    to ever return."""

    def test_deactivate_bundle_calls_manager(self):
        mock_bm = MagicMock()
        mock_bm.deactivate_bundle.return_value = {"bundle_id": "b1", "is_active": False}
        with patch.object(api_server, "get_bundle_manager", lambda: mock_bm):
            result = asyncio.run(api_server.deactivate_bundle("b1", {"user_id": "creator1"}))
        mock_bm.deactivate_bundle.assert_called_once_with("b1", "creator1")
        self.assertFalse(result["is_active"])

    def test_activate_bundle_calls_manager(self):
        mock_bm = MagicMock()
        mock_bm.activate_bundle.return_value = {"bundle_id": "b1", "is_active": True}
        with patch.object(api_server, "get_bundle_manager", lambda: mock_bm):
            result = asyncio.run(api_server.activate_bundle("b1", {"user_id": "creator1"}))
        mock_bm.activate_bundle.assert_called_once_with("b1", "creator1")
        self.assertTrue(result["is_active"])

    def test_deactivate_non_owner_raises_403(self):
        mock_bm = MagicMock()
        mock_bm.deactivate_bundle.side_effect = PermissionError("このバンドルの作成者のみが操作できます")
        with patch.object(api_server, "get_bundle_manager", lambda: mock_bm):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.deactivate_bundle("b1", {"user_id": "not-owner"}))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_activate_unknown_bundle_raises_404(self):
        mock_bm = MagicMock()
        mock_bm.activate_bundle.side_effect = ValueError("バンドルが見つかりません")
        with patch.object(api_server, "get_bundle_manager", lambda: mock_bm):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.activate_bundle("no-such-id", {"user_id": "creator1"}))
        self.assertEqual(ctx.exception.status_code, 404)


class TestLegacyTwoFactorEndpoints(unittest.TestCase):
    """POST /api/2fa/enable and /api/2fa/verify-backup, exercised against a
    real TwoFactorAuthService (same pattern as tests/test_two_factor_auth.py)
    rather than mocks, since both bugs fixed here were invisible to mocked
    tests -- they were about the REAL underlying service/name resolution.
    """

    def setUp(self):
        self._saved_secret = os.environ.get("COCOA_2FA_SECRET")
        os.environ["COCOA_2FA_SECRET"] = "test-only-secret-not-for-production"
        # Fresh singleton per test so state doesn't leak across tests.
        import two_factor_auth as tfa_module
        tfa_module._two_factor_service = None

        # api_server.py imports setup_2fa/get_two_factor_service/etc via
        # `from .two_factor_auth import ...` (relative). This test file
        # bare-imports api_server (sys.path.insert + `import api_server`,
        # no parent package -- same as every other test in this file), which
        # makes that relative import fail and fall back to None for all of
        # them -- a test-harness-only artifact (verified earlier this
        # session: a proper `import main.api_server` package import resolves
        # these correctly, matching how uvicorn loads it in production).
        # Patch them directly to the real functions so these tests exercise
        # the real 2FA logic instead of the None-fallback 404 path.
        for name in ("setup_2fa", "get_two_factor_service", "verify_2fa_token", "verify_backup_code"):
            patcher = patch.object(api_server, name, getattr(tfa_module, name))
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        if self._saved_secret is None:
            os.environ.pop("COCOA_2FA_SECRET", None)
        else:
            os.environ["COCOA_2FA_SECRET"] = self._saved_secret
        import two_factor_auth as tfa_module
        tfa_module._two_factor_service = None

    def test_enable_with_wrong_token_does_not_persist(self):
        user = {"user_id": 501, "username": "alice"}
        asyncio.run(api_server.setup_two_factor_auth("alice", user))
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(api_server.enable_two_factor_auth("alice", "000000", user))
        self.assertEqual(ctx.exception.status_code, 400)
        status = api_server.get_two_factor_service().get_user_2fa_status(501)
        self.assertFalse(status.get("is_enabled"))

    def test_enable_with_correct_token_persists(self):
        from two_factor_auth import TOTPGenerator
        user = {"user_id": 502, "username": "bob"}
        setup_result = asyncio.run(api_server.setup_two_factor_auth("bob", user))
        secret = setup_result["setup_data"]["secret"]
        token = TOTPGenerator(secret).generate_token()

        result = asyncio.run(api_server.enable_two_factor_auth("bob", token, user))
        self.assertEqual(result["status"], "enabled")

        status = api_server.get_two_factor_service().get_user_2fa_status(502)
        self.assertTrue(status.get("is_enabled"))

    def test_enable_does_not_regenerate_the_secret(self):
        # The original bug called setup_2fa() again inside enable, silently
        # replacing the secret the user already scanned into their
        # authenticator app -- verifying against the ORIGINAL secret must
        # still work after a successful enable.
        from two_factor_auth import TOTPGenerator
        user = {"user_id": 503, "username": "carol"}
        setup_result = asyncio.run(api_server.setup_two_factor_auth("carol", user))
        secret = setup_result["setup_data"]["secret"]
        token = TOTPGenerator(secret).generate_token()
        asyncio.run(api_server.enable_two_factor_auth("carol", token, user))

        next_token = TOTPGenerator(secret).generate_token()
        verify_result = asyncio.run(api_server.verify_two_factor_token("carol", next_token, user))
        self.assertTrue(verify_result["valid"])

    def test_verify_backup_code_accepts_real_code(self):
        # Before the fix, calling this endpoint always raised (the function
        # shadowed its own import), regardless of whether the code was valid.
        from two_factor_auth import TOTPGenerator
        user = {"user_id": 504, "username": "dave"}
        setup_result = asyncio.run(api_server.setup_two_factor_auth("dave", user))
        secret = setup_result["setup_data"]["secret"]
        token = TOTPGenerator(secret).generate_token()
        asyncio.run(api_server.enable_two_factor_auth("dave", token, user))

        backup_code = setup_result["setup_data"]["backup_codes"][0]
        result = asyncio.run(api_server.verify_two_factor_backup_code("dave", backup_code, user))
        self.assertTrue(result["valid"])

    def test_verify_backup_code_rejects_bogus_code(self):
        user = {"user_id": 505, "username": "erin"}
        asyncio.run(api_server.setup_two_factor_auth("erin", user))
        result = asyncio.run(api_server.verify_two_factor_backup_code("erin", "not-a-real-code", user))
        self.assertFalse(result["valid"])

    def test_verify_backup_code_is_single_use(self):
        from two_factor_auth import TOTPGenerator
        user = {"user_id": 506, "username": "frank"}
        setup_result = asyncio.run(api_server.setup_two_factor_auth("frank", user))
        secret = setup_result["setup_data"]["secret"]
        token = TOTPGenerator(secret).generate_token()
        asyncio.run(api_server.enable_two_factor_auth("frank", token, user))

        backup_code = setup_result["setup_data"]["backup_codes"][0]
        first = asyncio.run(api_server.verify_two_factor_backup_code("frank", backup_code, user))
        self.assertTrue(first["valid"])
        second = asyncio.run(api_server.verify_two_factor_backup_code("frank", backup_code, user))
        self.assertFalse(second["valid"])


class TestCheckoutIdempotency(unittest.TestCase):
    """checkout_cart / purchase_bundle honour an Idempotency-Key so a retried
    request (e.g. after a network timeout) returns the ORIGINAL result instead
    of charging again -- matching the gift/tip/gift-card endpoints. Uses a real
    IdempotencyStore since it's pure stdlib."""

    def _store(self):
        from idempotency import IdempotencyStore
        return IdempotencyStore()

    def test_checkout_same_key_charges_once_and_returns_original(self):
        store = self._store()
        calls = {"n": 0}

        def fake_checkout(uid, mp):
            calls["n"] += 1
            return {"success": True, "order": {"order_id": f"ord-{calls['n']}",
                                               "total_credits": 100, "items": []}, "failed_items": []}
        mock_cm = MagicMock()
        mock_cm.checkout.side_effect = fake_checkout
        mock_membership = MagicMock()

        with patch.object(api_server, "get_cart_manager", lambda: mock_cm), \
             patch.object(api_server, "get_marketplace", MagicMock()), \
             patch.object(api_server, "get_idempotency_store", lambda: store), \
             patch.object(api_server, "get_membership_manager", lambda: mock_membership), \
             patch.object(api_server, "get_referral_manager", None), \
             patch.object(api_server, "get_license_manager", None), \
             patch.object(api_server, "get_notification_queue", None):
            user = {"user_id": "u1", "username": "alice"}
            r1 = asyncio.run(api_server.checkout_cart(user, idempotency_key="k1"))
            r2 = asyncio.run(api_server.checkout_cart(user, idempotency_key="k1"))

        self.assertEqual(calls["n"], 1)  # charged exactly once
        self.assertEqual(r1["order"]["order_id"], r2["order"]["order_id"])  # same order returned
        # One-time side effect (tier tracking) must not re-fire on the replay.
        self.assertEqual(mock_membership.record_purchase.call_count, 1)

    def test_checkout_no_key_runs_every_time(self):
        store = self._store()
        calls = {"n": 0}

        def fake_checkout(uid, mp):
            calls["n"] += 1
            return {"success": True, "order": {"order_id": f"o{calls['n']}",
                                               "total_credits": 0, "items": []}, "failed_items": []}
        mock_cm = MagicMock()
        mock_cm.checkout.side_effect = fake_checkout

        with patch.object(api_server, "get_cart_manager", lambda: mock_cm), \
             patch.object(api_server, "get_marketplace", MagicMock()), \
             patch.object(api_server, "get_idempotency_store", lambda: store), \
             patch.object(api_server, "get_membership_manager", None), \
             patch.object(api_server, "get_referral_manager", None), \
             patch.object(api_server, "get_license_manager", None), \
             patch.object(api_server, "get_notification_queue", None):
            user = {"user_id": "u1", "username": "alice"}
            asyncio.run(api_server.checkout_cart(user, idempotency_key=None))
            asyncio.run(api_server.checkout_cart(user, idempotency_key=None))

        self.assertEqual(calls["n"], 2)  # no idempotency requested → runs each time

    def test_checkout_different_keys_are_independent(self):
        store = self._store()
        calls = {"n": 0}

        def fake_checkout(uid, mp):
            calls["n"] += 1
            return {"success": True, "order": {"order_id": f"o{calls['n']}",
                                               "total_credits": 0, "items": []}, "failed_items": []}
        mock_cm = MagicMock()
        mock_cm.checkout.side_effect = fake_checkout

        with patch.object(api_server, "get_cart_manager", lambda: mock_cm), \
             patch.object(api_server, "get_marketplace", MagicMock()), \
             patch.object(api_server, "get_idempotency_store", lambda: store), \
             patch.object(api_server, "get_membership_manager", None), \
             patch.object(api_server, "get_referral_manager", None), \
             patch.object(api_server, "get_license_manager", None), \
             patch.object(api_server, "get_notification_queue", None):
            user = {"user_id": "u1", "username": "alice"}
            asyncio.run(api_server.checkout_cart(user, idempotency_key="k1"))
            asyncio.run(api_server.checkout_cart(user, idempotency_key="k2"))

        self.assertEqual(calls["n"], 2)  # distinct keys → two genuine checkouts

    def test_idempotency_key_is_scoped_per_user(self):
        # Two different users sending the same client-chosen key must NOT
        # collide -- the stored key is prefixed with the user id.
        store = self._store()
        calls = {"n": 0}

        def fake_checkout(uid, mp):
            calls["n"] += 1
            return {"success": True, "order": {"order_id": f"{uid}-{calls['n']}",
                                               "total_credits": 0, "items": []}, "failed_items": []}
        mock_cm = MagicMock()
        mock_cm.checkout.side_effect = fake_checkout

        with patch.object(api_server, "get_cart_manager", lambda: mock_cm), \
             patch.object(api_server, "get_marketplace", MagicMock()), \
             patch.object(api_server, "get_idempotency_store", lambda: store), \
             patch.object(api_server, "get_membership_manager", None), \
             patch.object(api_server, "get_referral_manager", None), \
             patch.object(api_server, "get_license_manager", None), \
             patch.object(api_server, "get_notification_queue", None):
            asyncio.run(api_server.checkout_cart({"user_id": "u1", "username": "a"}, idempotency_key="same"))
            asyncio.run(api_server.checkout_cart({"user_id": "u2", "username": "b"}, idempotency_key="same"))

        self.assertEqual(calls["n"], 2)  # same raw key, different users → not a collision

    def test_bundle_same_key_charges_once(self):
        store = self._store()
        calls = {"n": 0}

        def fake_purchase(bid, uid, mp, cart):
            calls["n"] += 1
            return {"purchased": [], "total_charged": 50, "result_id": calls["n"]}
        mock_bm = MagicMock()
        mock_bm.purchase_bundle.side_effect = fake_purchase

        with patch.object(api_server, "get_bundle_manager", lambda: mock_bm), \
             patch.object(api_server, "get_marketplace", MagicMock()), \
             patch.object(api_server, "get_cart_manager", None), \
             patch.object(api_server, "get_idempotency_store", lambda: store), \
             patch.object(api_server, "get_membership_manager", None), \
             patch.object(api_server, "get_referral_manager", None), \
             patch.object(api_server, "get_license_manager", None), \
             patch.object(api_server, "get_notification_queue", None):
            user = {"user_id": "u1", "username": "alice"}
            b1 = asyncio.run(api_server.purchase_bundle("bnd1", user, idempotency_key="k1"))
            b2 = asyncio.run(api_server.purchase_bundle("bnd1", user, idempotency_key="k1"))

        self.assertEqual(calls["n"], 1)
        self.assertEqual(b1["result_id"], b2["result_id"])

    def test_failed_checkout_is_not_cached(self):
        # A checkout that raises (e.g. empty cart) must NOT be memoized -- the
        # user must be able to retry with the same key after fixing the cart.
        store = self._store()
        calls = {"n": 0}

        def fake_checkout(uid, mp):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ValueError("カートが空です")
            return {"success": True, "order": {"order_id": "ord-real",
                                               "total_credits": 0, "items": []}, "failed_items": []}
        mock_cm = MagicMock()
        mock_cm.checkout.side_effect = fake_checkout

        with patch.object(api_server, "get_cart_manager", lambda: mock_cm), \
             patch.object(api_server, "get_marketplace", MagicMock()), \
             patch.object(api_server, "get_idempotency_store", lambda: store), \
             patch.object(api_server, "get_membership_manager", None), \
             patch.object(api_server, "get_referral_manager", None), \
             patch.object(api_server, "get_license_manager", None), \
             patch.object(api_server, "get_notification_queue", None):
            user = {"user_id": "u1", "username": "alice"}
            with self.assertRaises(Exception):
                asyncio.run(api_server.checkout_cart(user, idempotency_key="k1"))
            # Retry with the SAME key must actually re-run (failure wasn't cached).
            r = asyncio.run(api_server.checkout_cart(user, idempotency_key="k1"))

        self.assertEqual(calls["n"], 2)
        self.assertEqual(r["order"]["order_id"], "ord-real")


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestDisputeCommission(unittest.TestCase):
    """dispute_commission() surfaces a commission in the unified moderation
    queue (kind="commission_dispute", declared in moderation_queue.VALID_KINDS
    but unreachable until this endpoint existed) and notifies the other party."""

    def _fake_request(self, requester_id="u1", creator_id="u2", title="Cool avatar"):
        req = MagicMock()
        req.requester_id = requester_id
        req.creator_id = creator_id
        req.title = title
        return req

    def _body(self, reason="never delivered", details="waited 30 days"):
        body = MagicMock()
        body.reason = reason
        body.details = details
        return body

    def test_requester_can_dispute(self):
        req = self._fake_request()
        mock_cs = MagicMock()
        mock_cs.get.return_value = req
        mock_mq = MagicMock()
        mock_item = MagicMock()
        mock_item.to_dict.return_value = {"item_id": "m1", "kind": "commission_dispute"}
        mock_mq.enqueue.return_value = mock_item
        mock_nq = MagicMock()

        with patch.object(api_server, "get_commission_store", lambda: mock_cs), \
             patch.object(api_server, "get_moderation_queue", lambda: mock_mq), \
             patch.object(api_server, "get_notification_queue", lambda: mock_nq):
            result = asyncio.run(api_server.dispute_commission(
                "req-1", self._body(), {"user_id": "u1"}
            ))

        self.assertEqual(result["kind"], "commission_dispute")
        mock_mq.enqueue.assert_called_once()
        kwargs = mock_mq.enqueue.call_args.kwargs
        self.assertEqual(kwargs["kind"], "commission_dispute")
        self.assertEqual(kwargs["source_id"], "commission_dispute:req-1")
        self.assertEqual(kwargs["subject_id"], "req-1")
        self.assertEqual(kwargs["reporter_id"], "u1")

    def test_creator_can_dispute(self):
        req = self._fake_request()
        mock_cs = MagicMock()
        mock_cs.get.return_value = req
        mock_mq = MagicMock()
        mock_mq.enqueue.return_value.to_dict.return_value = {"item_id": "m1"}

        with patch.object(api_server, "get_commission_store", lambda: mock_cs), \
             patch.object(api_server, "get_moderation_queue", lambda: mock_mq), \
             patch.object(api_server, "get_notification_queue", None):
            asyncio.run(api_server.dispute_commission(
                "req-1", self._body(), {"user_id": "u2"}
            ))

        kwargs = mock_mq.enqueue.call_args.kwargs
        self.assertEqual(kwargs["reporter_id"], "u2")

    def test_stranger_cannot_dispute(self):
        req = self._fake_request()
        mock_cs = MagicMock()
        mock_cs.get.return_value = req
        mock_mq = MagicMock()

        with patch.object(api_server, "get_commission_store", lambda: mock_cs), \
             patch.object(api_server, "get_moderation_queue", lambda: mock_mq), \
             patch.object(api_server, "get_notification_queue", None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.dispute_commission(
                    "req-1", self._body(), {"user_id": "u3"}
                ))
        self.assertEqual(ctx.exception.status_code, 403)
        mock_mq.enqueue.assert_not_called()

    def test_unknown_commission_raises_404(self):
        mock_cs = MagicMock()
        mock_cs.get.return_value = None
        mock_mq = MagicMock()

        with patch.object(api_server, "get_commission_store", lambda: mock_cs), \
             patch.object(api_server, "get_moderation_queue", lambda: mock_mq), \
             patch.object(api_server, "get_notification_queue", None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.dispute_commission(
                    "no-such-id", self._body(), {"user_id": "u1"}
                ))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_empty_reason_raises_400(self):
        req = self._fake_request()
        mock_cs = MagicMock()
        mock_cs.get.return_value = req
        mock_mq = MagicMock()

        with patch.object(api_server, "get_commission_store", lambda: mock_cs), \
             patch.object(api_server, "get_moderation_queue", lambda: mock_mq), \
             patch.object(api_server, "get_notification_queue", None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.dispute_commission(
                    "req-1", self._body(reason="   "), {"user_id": "u1"}
                ))
        self.assertEqual(ctx.exception.status_code, 400)
        mock_mq.enqueue.assert_not_called()

    def test_notifies_the_other_party_not_the_disputer(self):
        req = self._fake_request(requester_id="u1", creator_id="u2")
        mock_cs = MagicMock()
        mock_cs.get.return_value = req
        mock_mq = MagicMock()
        mock_mq.enqueue.return_value.to_dict.return_value = {"item_id": "m1"}
        mock_nq = MagicMock()

        with patch.object(api_server, "get_commission_store", lambda: mock_cs), \
             patch.object(api_server, "get_moderation_queue", lambda: mock_mq), \
             patch.object(api_server, "get_notification_queue", lambda: mock_nq):
            asyncio.run(api_server.dispute_commission(
                "req-1", self._body(), {"user_id": "u1"}
            ))

        mock_nq.push.assert_called_once()
        args = mock_nq.push.call_args[0]
        self.assertEqual(args[0], "u2")  # creator, not the disputing requester
        self.assertEqual(args[1], "commission_disputed")

    def test_notification_failure_does_not_block_dispute(self):
        """The dispute itself must succeed even if the notification push fails
        (matches the established best-effort pattern elsewhere in api_server)."""
        req = self._fake_request()
        mock_cs = MagicMock()
        mock_cs.get.return_value = req
        mock_mq = MagicMock()
        mock_mq.enqueue.return_value.to_dict.return_value = {"item_id": "m1"}
        mock_nq = MagicMock()
        mock_nq.push.side_effect = RuntimeError("notification service down")

        with patch.object(api_server, "get_commission_store", lambda: mock_cs), \
             patch.object(api_server, "get_moderation_queue", lambda: mock_mq), \
             patch.object(api_server, "get_notification_queue", lambda: mock_nq):
            result = asyncio.run(api_server.dispute_commission(
                "req-1", self._body(), {"user_id": "u1"}
            ))
        self.assertEqual(result["item_id"], "m1")

    def test_moderation_queue_unavailable_raises_503(self):
        with patch.object(api_server, "get_commission_store", MagicMock()), \
             patch.object(api_server, "get_moderation_queue", None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.dispute_commission(
                    "req-1", self._body(), {"user_id": "u1"}
                ))
        self.assertEqual(ctx.exception.status_code, 503)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestRegisterSignupBonus(unittest.TestCase):
    """register() grants a one-time signup credit bonus so a brand-new,
    unreferred account has an actual entry point into the paid marketplace
    (previously the only ways to acquire a first credit were a gift card from
    someone who already had credits, or being someone else's referral)."""

    def _body(self, username="alice", email="alice@example.com", password="hunter22", referral_code=None):
        body = MagicMock()
        body.username = username
        body.email = email
        body.password = password
        body.referral_code = referral_code
        return body

    def _fake_user(self, user_id="u1", username="alice", role="user"):
        user = MagicMock()
        user.user_id = user_id
        user.username = username
        user.role = role
        user.is_email_verified = False
        return user

    def test_grants_signup_bonus_on_success(self):
        mock_auth = MagicMock()
        mock_auth.register.return_value = self._fake_user()
        mock_auth.create_email_verification_token.return_value = "tok123"
        mock_mp = MagicMock()

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "get_marketplace", lambda: mock_mp):
            result = asyncio.run(api_server.register(self._body()))

        self.assertEqual(result["status"], "created")
        mock_mp.credit.assert_called_once_with(
            "u1", api_server._SIGNUP_BONUS_CREDITS, "signup_bonus", ref_id="u1"
        )

    def test_registration_succeeds_even_if_marketplace_credit_fails(self):
        """Registration must not fail just because the bonus grant errored --
        the account itself already exists at that point."""
        mock_auth = MagicMock()
        mock_auth.register.return_value = self._fake_user()
        mock_auth.create_email_verification_token.return_value = "tok123"
        mock_mp = MagicMock()
        mock_mp.credit.side_effect = RuntimeError("marketplace store down")

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "get_marketplace", lambda: mock_mp):
            result = asyncio.run(api_server.register(self._body()))

        self.assertEqual(result["status"], "created")

    def test_registration_succeeds_when_marketplace_unavailable(self):
        mock_auth = MagicMock()
        mock_auth.register.return_value = self._fake_user()
        mock_auth.create_email_verification_token.return_value = "tok123"

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "get_marketplace", None):
            result = asyncio.run(api_server.register(self._body()))

        self.assertEqual(result["status"], "created")

    def test_duplicate_registration_raises_before_any_bonus_call(self):
        mock_auth = MagicMock()
        mock_auth.register.side_effect = ValueError("username already exists")
        mock_mp = MagicMock()

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "get_marketplace", lambda: mock_mp):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.register(self._body()))

        self.assertEqual(ctx.exception.status_code, 400)
        mock_mp.credit.assert_not_called()

    def test_referral_code_applied_on_registration(self):
        # Regression: ReferralManager.apply_referral_code() was fully
        # implemented and covered its own unit tests, but register() never
        # called it -- there was no way for a real signup to ever redeem a
        # referral code, making the entire program dead in practice.
        mock_auth = MagicMock()
        mock_auth.register.return_value = self._fake_user()
        mock_auth.create_email_verification_token.return_value = "tok123"
        mock_mp = MagicMock()
        mock_ref = MagicMock()

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "get_marketplace", lambda: mock_mp), \
             patch.object(api_server, "get_referral_manager", lambda: mock_ref):
            result = asyncio.run(api_server.register(self._body(referral_code="ABC123")))

        self.assertEqual(result["status"], "created")
        mock_ref.apply_referral_code.assert_called_once_with("u1", "ABC123")

    def test_no_referral_code_skips_apply(self):
        mock_auth = MagicMock()
        mock_auth.register.return_value = self._fake_user()
        mock_auth.create_email_verification_token.return_value = "tok123"
        mock_mp = MagicMock()
        mock_ref = MagicMock()

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "get_marketplace", lambda: mock_mp), \
             patch.object(api_server, "get_referral_manager", lambda: mock_ref):
            asyncio.run(api_server.register(self._body(referral_code=None)))

        mock_ref.apply_referral_code.assert_not_called()

    def test_registration_succeeds_even_if_referral_apply_fails(self):
        # Same "already succeeded, must not roll back" guarantee as the
        # signup-bonus credit grant: a self-referral ValueError or any other
        # failure in apply_referral_code() must not fail the registration.
        mock_auth = MagicMock()
        mock_auth.register.return_value = self._fake_user()
        mock_auth.create_email_verification_token.return_value = "tok123"
        mock_mp = MagicMock()
        mock_ref = MagicMock()
        mock_ref.apply_referral_code.side_effect = ValueError("自分の招待コードは使用できません")

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "get_marketplace", lambda: mock_mp), \
             patch.object(api_server, "get_referral_manager", lambda: mock_ref):
            result = asyncio.run(api_server.register(self._body(referral_code="OWNCODE")))

        self.assertEqual(result["status"], "created")

    def test_registration_succeeds_when_referral_manager_unavailable(self):
        mock_auth = MagicMock()
        mock_auth.register.return_value = self._fake_user()
        mock_auth.create_email_verification_token.return_value = "tok123"
        mock_mp = MagicMock()

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "get_marketplace", lambda: mock_mp), \
             patch.object(api_server, "get_referral_manager", None):
            result = asyncio.run(api_server.register(self._body(referral_code="ABC123")))

        self.assertEqual(result["status"], "created")


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestLoginTwoFactor(unittest.TestCase):
    """login() and the new /api/auth/login/verify-2fa endpoint. _wire_auth_2fa
    is patched to a no-op in every test here -- these tests exercise the
    endpoint's own branching logic (isinstance(tokens, PendingTwoFactor)),
    not the wiring helper itself (already covered end-to-end manually against
    real AuthManager/TwoFactorAuthService instances)."""

    def _body(self, username="alice", password="hunter22"):
        body = MagicMock()
        body.username = username
        body.password = password
        return body

    def _verify_body(self, pending_token="pend-abc", code="123456", is_backup_code=False):
        body = MagicMock()
        body.pending_token = pending_token
        body.code = code
        body.is_backup_code = is_backup_code
        return body

    def test_login_without_2fa_returns_tokens_unchanged(self):
        mock_auth = MagicMock()
        mock_auth.login.return_value = TokenPair(access_token="acc", refresh_token="ref")

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "_wire_auth_2fa", lambda: None):
            result = asyncio.run(api_server.login(self._body()))

        self.assertEqual(result["access_token"], "acc")
        self.assertEqual(result["refresh_token"], "ref")
        self.assertNotIn("requires_2fa", result)

    def test_login_with_2fa_enabled_returns_pending_shape(self):
        mock_auth = MagicMock()
        mock_auth.login.return_value = PendingTwoFactor(pending_token="pend-xyz")

        # login()'s isinstance(tokens, PendingTwoFactor) check reads the name
        # from api_server's own module namespace at call time. Under this
        # test file's bare `import api_server` (no parent package), api_server's
        # internal `from .auth_manager import ...` fails and PendingTwoFactor
        # falls back to a dummy placeholder class distinct from the real one
        # this test constructs above -- patch it to the real class so the
        # isinstance check behaves as it does in production (where api_server
        # is loaded as main.api_server, a proper package import that resolves
        # the real class without needing this patch).
        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "_wire_auth_2fa", lambda: None), \
             patch.object(api_server, "PendingTwoFactor", PendingTwoFactor):
            result = asyncio.run(api_server.login(self._body()))

        self.assertTrue(result["requires_2fa"])
        self.assertEqual(result["pending_token"], "pend-xyz")
        self.assertNotIn("access_token", result)
        self.assertNotIn("refresh_token", result)

    def test_login_wrong_password_still_401(self):
        mock_auth = MagicMock()
        mock_auth.login.side_effect = AuthError("invalid_credentials", "bad creds")

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "_wire_auth_2fa", lambda: None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.login(self._body()))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_login_account_locked_returns_429(self):
        mock_auth = MagicMock()
        mock_auth.login.side_effect = AuthError("account_locked", "locked")

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "_wire_auth_2fa", lambda: None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.login(self._body()))
        self.assertEqual(ctx.exception.status_code, 429)

    def test_verify_2fa_success_returns_token_shape(self):
        mock_auth = MagicMock()
        mock_auth.complete_login_with_2fa.return_value = TokenPair(access_token="acc2", refresh_token="ref2")

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "_wire_auth_2fa", lambda: None):
            result = asyncio.run(api_server.verify_two_factor_login(self._verify_body()))

        self.assertEqual(result["access_token"], "acc2")
        self.assertEqual(result["refresh_token"], "ref2")
        mock_auth.complete_login_with_2fa.assert_called_once_with("pend-abc", "123456", False)

    def test_verify_2fa_passes_is_backup_code_flag(self):
        mock_auth = MagicMock()
        mock_auth.complete_login_with_2fa.return_value = TokenPair(access_token="a", refresh_token="r")

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "_wire_auth_2fa", lambda: None):
            asyncio.run(api_server.verify_two_factor_login(
                self._verify_body(code="AAAA1111", is_backup_code=True)
            ))

        mock_auth.complete_login_with_2fa.assert_called_once_with("pend-abc", "AAAA1111", True)

    def test_verify_2fa_wrong_code_returns_401(self):
        mock_auth = MagicMock()
        mock_auth.complete_login_with_2fa.side_effect = AuthError("invalid_2fa_code", "wrong code")

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "_wire_auth_2fa", lambda: None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.verify_two_factor_login(self._verify_body()))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_verify_2fa_expired_pending_token_returns_401(self):
        mock_auth = MagicMock()
        mock_auth.complete_login_with_2fa.side_effect = AuthError("token_invalid", "expired")

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "_wire_auth_2fa", lambda: None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.verify_two_factor_login(self._verify_body()))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_login_unavailable_raises_503(self):
        with patch.object(api_server, "get_auth_manager", None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.login(self._body()))
        self.assertEqual(ctx.exception.status_code, 503)

    def test_verify_2fa_unavailable_raises_503(self):
        with patch.object(api_server, "get_auth_manager", None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.verify_two_factor_login(self._verify_body()))
        self.assertEqual(ctx.exception.status_code, 503)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestPrometheusMetricsEndpoint(unittest.TestCase):
    """GET /metrics/prometheus: unauthenticated (a scraper never presents
    credentials), returns the real Prometheus text exposition format, and
    must never block the event loop on the underlying psutil call."""

    def test_returns_prometheus_format_response(self):
        mock_monitor = MagicMock()
        mock_monitor.expose_metrics.return_value = b"# HELP cocoa_up 1\ncocoa_up 1\n"
        mock_monitor.get_content_type.return_value = "text/plain; version=0.0.4"

        with patch.object(api_server, "get_prometheus_monitor", lambda: mock_monitor), \
             patch.object(api_server, "PROMETHEUS_AVAILABLE", True):
            result = asyncio.run(api_server.get_prometheus_metrics())

        mock_monitor.update_system_metrics.assert_called_once()
        self.assertEqual(result.body, b"# HELP cocoa_up 1\ncocoa_up 1\n")
        self.assertEqual(result.media_type, "text/plain; version=0.0.4")

    def test_unavailable_when_no_monitor_factory(self):
        with patch.object(api_server, "get_prometheus_monitor", None), \
             patch.object(api_server, "PROMETHEUS_AVAILABLE", True):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.get_prometheus_metrics())
        self.assertEqual(ctx.exception.status_code, 503)

    def test_unavailable_when_prometheus_client_missing(self):
        mock_monitor = MagicMock()
        with patch.object(api_server, "get_prometheus_monitor", lambda: mock_monitor), \
             patch.object(api_server, "PROMETHEUS_AVAILABLE", False):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.get_prometheus_metrics())
        self.assertEqual(ctx.exception.status_code, 503)
        mock_monitor.update_system_metrics.assert_not_called()


class TestSpaRouteHelpers(unittest.TestCase):
    """_is_spa_route()/_is_frontend_dist_available(): the SPA catch-all
    (registered last, after every real route) must never shadow the
    backend's own reserved top-level prefixes -- a typo'd /api/* path must
    still 404, not silently serve index.html."""

    def test_backend_reserved_prefixes_are_not_spa_routes(self):
        for path in ("api/marketplace", "api/nonexistent", "docs", "redoc",
                     "openapi.json", "health", "metrics", "backups",
                     "security", "ws", "assets/index.js"):
            with self.subTest(path=path):
                self.assertFalse(api_server._is_spa_route(path))

    def test_client_routes_are_spa_routes(self):
        for path in ("", "login", "register", "cart", "collections",
                     "me", "me/security", "me/orders", "listings/abc123"):
            with self.subTest(path=path):
                self.assertTrue(api_server._is_spa_route(path))

    def test_only_first_segment_is_checked(self):
        # A client route that merely CONTAINS a reserved word later in the
        # path must not be misclassified -- only the first segment counts.
        self.assertTrue(api_server._is_spa_route("collections/api-tools"))

    def test_dist_unavailable_when_no_index_html(self):
        with patch.object(api_server, "_FRONTEND_INDEX_HTML", Path("/nonexistent/index.html")):
            self.assertFalse(api_server._is_frontend_dist_available())

    def test_dist_available_when_index_html_present(self):
        with patch.object(api_server, "_FRONTEND_INDEX_HTML", Path(__file__)):  # any real file
            self.assertTrue(api_server._is_frontend_dist_available())


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestSpaFallbackEndpoint(unittest.TestCase):
    """spa_fallback(): the actual route handler, not just its helpers."""

    def test_serves_index_html_for_client_route_when_dist_available(self):
        with patch.object(api_server, "_is_frontend_dist_available", lambda: True), \
             patch.object(api_server, "_FRONTEND_INDEX_HTML", Path(__file__)), \
             patch.object(api_server, "FileResponse", lambda path: {"served": path}):
            result = asyncio.run(api_server.spa_fallback("me/security"))
        self.assertEqual(result, {"served": str(Path(__file__))})

    def test_404s_for_reserved_prefix_even_when_dist_available(self):
        with patch.object(api_server, "_is_frontend_dist_available", lambda: True):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.spa_fallback("api/nonexistent"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_404s_when_dist_unavailable(self):
        with patch.object(api_server, "_is_frontend_dist_available", lambda: False):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.spa_fallback("login"))
        self.assertEqual(ctx.exception.status_code, 404)


class TestParseCorsOrigins(unittest.TestCase):
    """_parse_cors_origins(): COCOA_CORS_ORIGINS parsing, with a fallback to
    the dev-server defaults so local development is unaffected by this
    change."""

    def test_none_falls_back_to_dev_defaults(self):
        self.assertEqual(
            api_server._parse_cors_origins(None),
            ["http://localhost:3000", "http://localhost:5173"],
        )

    def test_empty_string_falls_back_to_dev_defaults(self):
        self.assertEqual(
            api_server._parse_cors_origins(""),
            ["http://localhost:3000", "http://localhost:5173"],
        )

    def test_whitespace_only_falls_back_to_dev_defaults(self):
        self.assertEqual(
            api_server._parse_cors_origins("   "),
            ["http://localhost:3000", "http://localhost:5173"],
        )

    def test_single_origin(self):
        self.assertEqual(
            api_server._parse_cors_origins("https://cocoa.example.com"),
            ["https://cocoa.example.com"],
        )

    def test_multiple_origins_with_surrounding_whitespace_trimmed(self):
        self.assertEqual(
            api_server._parse_cors_origins("https://a.example.com, https://b.example.com"),
            ["https://a.example.com", "https://b.example.com"],
        )

    def test_trailing_comma_does_not_add_empty_origin(self):
        self.assertEqual(
            api_server._parse_cors_origins("https://a.example.com,"),
            ["https://a.example.com"],
        )

    def test_only_commas_falls_back_to_dev_defaults(self):
        self.assertEqual(
            api_server._parse_cors_origins(",,,"),
            ["http://localhost:3000", "http://localhost:5173"],
        )


class TestRequestEndpointLabel(unittest.TestCase):
    """_request_endpoint_label(): labels a request by its matched route
    TEMPLATE (bounded cardinality), never the raw path."""

    def _req(self, scope):
        req = MagicMock()
        req.scope = scope
        return req

    def test_uses_matched_route_template(self):
        route = MagicMock()
        route.path = "/api/collections/{collection_id}"
        label = api_server._request_endpoint_label(self._req({"route": route}))
        self.assertEqual(label, "/api/collections/{collection_id}")

    def test_no_route_falls_back_to_unmatched(self):
        self.assertEqual(api_server._request_endpoint_label(self._req({})), "unmatched")

    def test_route_with_none_path_falls_back(self):
        route = MagicMock()
        route.path = None
        self.assertEqual(api_server._request_endpoint_label(self._req({"route": route})), "unmatched")

    def test_request_without_scope_attr_falls_back(self):
        bare = object()  # no .scope attribute at all
        self.assertEqual(api_server._request_endpoint_label(bare), "unmatched")


class TestRecordRequestMetrics(unittest.TestCase):
    """_record_request_metrics(): best-effort per-request instrumentation.
    Must record both the request counter and the latency histogram when
    Prometheus is available, no-op when it is not, and never let an exception
    from the monitor escape into the request path."""

    def _req(self, path="/api/x/{id}", method="GET"):
        req = MagicMock()
        req.method = method
        route = MagicMock()
        route.path = path
        req.scope = {"route": route}
        return req

    def test_records_counter_and_histogram_when_available(self):
        mon = MagicMock()
        with patch.object(api_server, "get_prometheus_monitor", lambda: mon), \
             patch.object(api_server, "PROMETHEUS_AVAILABLE", True):
            api_server._record_request_metrics(self._req(), 200, 0.0)
        mon.record_request.assert_called_once_with("GET", "/api/x/{id}", 200)
        self.assertEqual(mon.observe_request_duration.call_count, 1)
        op, duration = mon.observe_request_duration.call_args.args
        self.assertEqual(op, "/api/x/{id}")
        self.assertGreaterEqual(duration, 0.0)

    def test_noop_when_prometheus_unavailable(self):
        mon = MagicMock()
        with patch.object(api_server, "get_prometheus_monitor", lambda: mon), \
             patch.object(api_server, "PROMETHEUS_AVAILABLE", False):
            api_server._record_request_metrics(self._req(), 200, 0.0)
        mon.record_request.assert_not_called()
        mon.observe_request_duration.assert_not_called()

    def test_noop_when_no_monitor_factory(self):
        with patch.object(api_server, "get_prometheus_monitor", None), \
             patch.object(api_server, "PROMETHEUS_AVAILABLE", True):
            # Must not raise despite get_prometheus_monitor being None.
            api_server._record_request_metrics(self._req(), 200, 0.0)

    def test_monitor_exception_is_swallowed(self):
        mon = MagicMock()
        mon.record_request.side_effect = RuntimeError("prometheus internal boom")
        with patch.object(api_server, "get_prometheus_monitor", lambda: mon), \
             patch.object(api_server, "PROMETHEUS_AVAILABLE", True):
            # A broken monitor must never break the response.
            api_server._record_request_metrics(self._req(), 500, 0.0)

    def test_rate_limited_request_labelled_unmatched(self):
        # A request rejected before routing has no route in scope -- it must
        # collapse to "unmatched", not the raw path (cardinality safety).
        mon = MagicMock()
        req = MagicMock()
        req.method = "POST"
        req.scope = {}
        with patch.object(api_server, "get_prometheus_monitor", lambda: mon), \
             patch.object(api_server, "PROMETHEUS_AVAILABLE", True):
            api_server._record_request_metrics(req, 429, 0.0)
        mon.record_request.assert_called_once_with("POST", "unmatched", 429)


class TestCascadeDeleteUserData(unittest.TestCase):
    """_cascade_delete_user_data(): shared by the admin and self-service
    delete endpoints. Deliberately does NOT touch credit balance/ledger,
    commissions, referral codes, membership tier, or license keys -- see the
    function's own docstring / FEATURE_AUDIT.md 3-3 for why."""

    def _mocks(self):
        mock_mp = MagicMock()
        mock_mp.deactivate_all_listings.return_value = ["lid-1", "lid-2"]
        mock_idx = MagicMock()
        mock_cart = MagicMock()
        mock_wishlist = MagicMock()
        mock_collections = MagicMock()
        mock_collections.delete_all_for_owner.return_value = 3
        mock_searches = MagicMock()
        mock_searches.delete_all_for_user.return_value = 2
        mock_notifs = MagicMock()
        mock_notifs.delete_all_for_user.return_value = 5
        mock_2fa_service = MagicMock()
        return {
            "get_marketplace": lambda: mock_mp,
            "get_search_index": lambda: mock_idx,
            "get_cart_manager": lambda: mock_cart,
            "get_wishlist_manager": lambda: mock_wishlist,
            "get_collection_store": lambda: mock_collections,
            "get_saved_search_store": lambda: mock_searches,
            "get_notification_queue": lambda: mock_notifs,
            "get_two_factor_service": lambda: mock_2fa_service,
        }, {
            "marketplace": mock_mp, "index": mock_idx, "cart": mock_cart,
            "wishlist": mock_wishlist, "collections": mock_collections,
            "searches": mock_searches, "notifs": mock_notifs, "tfa": mock_2fa_service,
        }

    def test_calls_every_store(self):
        patches, mocks = self._mocks()
        with patch.multiple(api_server, **patches):
            result = api_server._cascade_delete_user_data("u1")

        mocks["marketplace"].deactivate_all_listings.assert_called_once_with("u1")
        self.assertEqual(mocks["index"].remove.call_count, 2)
        mocks["cart"].clear_cart.assert_called_once_with("u1")
        mocks["wishlist"].clear_wishlist.assert_called_once_with("u1")
        mocks["collections"].delete_all_for_owner.assert_called_once_with("u1")
        mocks["searches"].delete_all_for_user.assert_called_once_with("u1")
        mocks["notifs"].delete_all_for_user.assert_called_once_with("u1")
        mocks["tfa"].store.delete.assert_called_once_with("u1")

        self.assertEqual(result["listings_deactivated"], 2)
        self.assertEqual(result["collections_deleted"], 3)
        self.assertEqual(result["saved_searches_deleted"], 2)
        self.assertEqual(result["notifications_deleted"], 5)

    def test_never_touches_credit_or_ledger(self):
        # No mock in this suite exposes a credit/debit/ledger method at all --
        # this test documents the invariant explicitly so a future edit that
        # adds such a call is caught by a NEW assertion failure here, not
        # silently passing an unrelated test.
        patches, mocks = self._mocks()
        with patch.multiple(api_server, **patches):
            api_server._cascade_delete_user_data("u1")
        mocks["marketplace"].credit.assert_not_called()
        mocks["marketplace"].debit.assert_not_called()

    def test_one_store_raising_does_not_block_the_others(self):
        patches, mocks = self._mocks()
        mocks["cart"].clear_cart.side_effect = RuntimeError("cart store down")
        with patch.multiple(api_server, **patches):
            result = api_server._cascade_delete_user_data("u1")
        # cart's own failure doesn't stop the rest from running.
        mocks["wishlist"].clear_wishlist.assert_called_once_with("u1")
        mocks["notifs"].delete_all_for_user.assert_called_once_with("u1")
        self.assertEqual(result["collections_deleted"], 3)

    def test_missing_stores_do_not_raise(self):
        with patch.multiple(
            api_server,
            get_marketplace=None, get_cart_manager=None, get_wishlist_manager=None,
            get_collection_store=None, get_saved_search_store=None,
            get_notification_queue=None, get_two_factor_service=None,
        ):
            result = api_server._cascade_delete_user_data("u1")
        self.assertEqual(result["listings_deactivated"], 0)
        self.assertEqual(result["collections_deleted"], 0)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestDeleteOwnAccountEndpoint(unittest.TestCase):
    """DELETE /api/auth/me -- self-service account deletion."""

    def _body(self, password="hunter22"):
        body = MagicMock()
        body.password = password
        return body

    def test_success_deletes_and_cascades(self):
        mock_auth = MagicMock()
        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "_cascade_delete_user_data", lambda uid: {"collections_deleted": 1}) as mock_cascade:
            result = asyncio.run(api_server.delete_own_account(
                self._body(), {"user_id": "u1"}
            ))

        mock_auth.delete_own_account.assert_called_once_with("u1", "hunter22")
        self.assertEqual(result["status"], "deleted")
        self.assertEqual(result["collections_deleted"], 1)

    def test_wrong_password_returns_400_and_no_cascade(self):
        mock_auth = MagicMock()
        mock_auth.delete_own_account.side_effect = AuthError("invalid_credentials", "wrong password")

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth) as _, \
             patch.object(api_server, "_cascade_delete_user_data") as mock_cascade:
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.delete_own_account(self._body(), {"user_id": "u1"}))

        self.assertEqual(ctx.exception.status_code, 400)
        mock_cascade.assert_not_called()

    def test_unavailable_raises_503(self):
        with patch.object(api_server, "get_auth_manager", None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.delete_own_account(self._body(), {"user_id": "u1"}))
        self.assertEqual(ctx.exception.status_code, 503)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestAdminDeleteUserCascade(unittest.TestCase):
    """DELETE /api/admin/users/{user_id} now also runs the shared cascade,
    on top of its pre-existing listing deactivation."""

    def test_response_includes_cascade_counts(self):
        mock_auth = MagicMock()
        mock_auth.store.delete_user.return_value = True

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "_cascade_delete_user_data",
                          lambda uid: {"listings_deactivated": 4, "collections_deleted": 2,
                                       "saved_searches_deleted": 1, "notifications_deleted": 0}):
            result = asyncio.run(api_server.delete_user("u1", {"user_id": "admin1", "role": "admin"}))

        self.assertEqual(result["status"], "deleted")
        self.assertEqual(result["listings_deactivated"], 4)
        self.assertEqual(result["collections_deleted"], 2)

    def test_unknown_user_returns_404_without_cascade(self):
        mock_auth = MagicMock()
        mock_auth.store.delete_user.return_value = False

        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "_cascade_delete_user_data") as mock_cascade:
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.delete_user("u1", {"user_id": "admin1", "role": "admin"}))

        self.assertEqual(ctx.exception.status_code, 404)
        mock_cascade.assert_not_called()


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestVRChatToolsPackagedImport(unittest.TestCase):
    """Regression: the VRChat tool endpoints imported their helper modules with
    a bare top-level `from vrchat_parameter_budget import ...`. That resolves
    only when main/ is directly on sys.path (loose-script runs), but under the
    canonical `uvicorn main.api_server:app` the file lives in the `main`
    package, so the bare import raised ImportError and the endpoint always
    returned 503 in production.

    The rest of this suite deliberately puts main/ on sys.path and imports
    api_server flat, so a bare import resolves here and would hide the bug.
    We therefore run the check in a SUBPROCESS from the repo root with the
    packaged import path (`import main.api_server`) — the exact context that
    failed — and assert the endpoint returns a real analysis, not the 503
    fallback (which surfaced as an HTTPException(503))."""

    def _run_packaged(self, snippet: str) -> subprocess.CompletedProcess:
        repo_root = str(Path(__file__).resolve().parent.parent)
        code = (
            "import asyncio\n"
            "import main.api_server as a\n"
            + snippet
        )
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_budget_endpoint_works_under_packaged_import(self):
        proc = self._run_packaged(
            "r = asyncio.run(a.analyze_vrchat_budget(a.VRChatBudgetRequest(parameters=["
            "{'name':'IsHappy','type':'Bool','synced':True},"
            "{'name':'Mode','type':'Int','synced':True}])))\n"
            "assert r['used_bits'] == 9, r\n"
            "assert r['over_budget'] is False, r\n"
            "assert 'suggestions' in r, r\n"
            "print('OK')\n"
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("OK", proc.stdout)

    def test_performance_endpoint_works_under_packaged_import(self):
        proc = self._run_packaged(
            "r = asyncio.run(a.analyze_vrchat_performance("
            "a.VRChatStatsRequest(polygons=50000, materials=2, platform='PC')))\n"
            "assert 'rank' in r, r\n"
            "assert 'suggestions' in r, r\n"
            "print('OK')\n"
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("OK", proc.stdout)

    def test_performance_endpoint_accepts_quest_platform(self):
        # Regression: the endpoint mapped "quest" to a nonexistent
        # Platform.Quest enum member, raising AttributeError -> HTTP 400 for
        # every Quest analysis. Quest is Android-based, so it must resolve to
        # the ANDROID limits and return a real rank.
        proc = self._run_packaged(
            "r = asyncio.run(a.analyze_vrchat_performance("
            "a.VRChatStatsRequest(polygons=80000, materials=8, platform='Quest')))\n"
            "assert 'rank' in r, r\n"
            "assert r['platform'] == 'Quest', r\n"
            "print('OK')\n"
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("OK", proc.stdout)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestEmailDeliveryAndTokenExposure(unittest.TestCase):
    """Reset/verification tokens must travel by email, not the API response.

    An in-band verification token lets anyone register with someone else's
    address and self-verify (the token proves mailbox ownership only if it
    travels through the mailbox); the reset token was simply never delivered
    at all in production, permanently locking out anyone who forgot their
    password.
    """

    def _register_body(self):
        body = MagicMock()
        body.username = "alice"
        body.email = "alice@example.com"
        body.password = "hunter22"
        body.referral_code = None
        return body

    def _fake_user(self):
        user = MagicMock()
        user.user_id = "u1"
        user.username = "alice"
        user.role = "user"
        user.email = "alice@example.com"
        user.is_email_verified = False
        return user

    def _register(self, expose=False):
        mock_auth = MagicMock()
        mock_auth.register.return_value = self._fake_user()
        mock_auth.create_email_verification_token.return_value = "tokV"
        env = {"COCOA_EXPOSE_VERIFY_TOKEN": "true"} if expose else {}
        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "get_marketplace", None), \
             patch.object(api_server, "send_email") as mock_send, \
             patch.dict(os.environ, env, clear=False):
            if not expose:
                os.environ.pop("COCOA_EXPOSE_VERIFY_TOKEN", None)
            result = asyncio.run(api_server.register(self._register_body()))
        return result, mock_send

    def test_register_does_not_return_verification_token_by_default(self):
        result, _ = self._register(expose=False)
        self.assertNotIn("email_verification_token", result)

    def test_register_returns_token_with_dev_optin(self):
        result, _ = self._register(expose=True)
        self.assertEqual(result["email_verification_token"], "tokV")

    def test_register_emails_the_verification_link(self):
        _, mock_send = self._register(expose=False)
        mock_send.assert_called_once()
        to, _subject, bodytext = mock_send.call_args[0]
        self.assertEqual(to, "alice@example.com")
        self.assertIn("/verify-email?token=tokV", bodytext)

    def test_resend_does_not_return_token_by_default(self):
        mock_auth = MagicMock()
        mock_auth.store.get_by_id.return_value = self._fake_user()
        mock_auth.create_email_verification_token.return_value = "tokR"
        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "send_email") as mock_send:
            os.environ.pop("COCOA_EXPOSE_VERIFY_TOKEN", None)
            result = asyncio.run(api_server.resend_verification({"user_id": "u1"}))
        self.assertNotIn("email_verification_token", result)
        to, _s, bodytext = mock_send.call_args[0]
        self.assertEqual(to, "alice@example.com")
        self.assertIn("/verify-email?token=tokR", bodytext)

    def test_password_reset_emails_the_reset_link(self):
        mock_auth = MagicMock()
        mock_auth.request_password_reset.return_value = "tokRESET"
        body = MagicMock()
        body.email = "alice@example.com"
        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "send_email") as mock_send:
            os.environ.pop("COCOA_EXPOSE_RESET_TOKEN", None)
            result = asyncio.run(api_server.request_password_reset(body))
        self.assertEqual(result, {"status": "sent"})
        to, _s, bodytext = mock_send.call_args[0]
        self.assertEqual(to, "alice@example.com")
        self.assertIn("/reset-password?token=tokRESET", bodytext)

    def test_password_reset_uniform_response_for_unknown_email(self):
        """Enumeration prevention: unknown address -> same response, no mail."""
        mock_auth = MagicMock()
        mock_auth.request_password_reset.return_value = None
        body = MagicMock()
        body.email = "nobody@example.com"
        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "send_email") as mock_send:
            result = asyncio.run(api_server.request_password_reset(body))
        self.assertEqual(result, {"status": "sent"})
        mock_send.assert_not_called()

    def test_mail_failure_does_not_break_registration(self):
        """send_email reports failure as False (it catches internally); the
        account must still be created and the endpoint still succeed."""
        mock_auth = MagicMock()
        mock_auth.register.return_value = self._fake_user()
        mock_auth.create_email_verification_token.return_value = "tokV"
        with patch.object(api_server, "get_auth_manager", lambda: mock_auth), \
             patch.object(api_server, "get_marketplace", None), \
             patch.object(api_server, "send_email", return_value=False):
            result = asyncio.run(api_server.register(self._register_body()))
        self.assertEqual(result["status"], "created")


class TestSubsystemImportIsolation(unittest.TestCase):
    """A broken module must not disable unrelated subsystems.

    The core subsystems used to be imported in one shared try/except, so a
    single failing module set every name to None at once -- one bad import
    silently turned the whole marketplace off.
    """

    def test_import_failure_is_isolated_to_that_module(self):
        missing = api_server._import_subsystem("definitely_not_a_real_module", "get_thing")
        self.assertEqual(missing, (None,))
        # The failure is recorded rather than swallowed...
        self.assertIn("definitely_not_a_real_module", api_server._SUBSYSTEM_ERRORS)
        # ...and unrelated subsystems are untouched.
        self.assertIsNotNone(api_server.get_marketplace)
        self.assertIsNotNone(api_server.get_auth_manager)
        api_server._SUBSYSTEM_ERRORS.pop("definitely_not_a_real_module", None)

    def test_missing_attribute_is_recorded(self):
        (attr,) = api_server._import_subsystem("avatar_marketplace", "no_such_attribute")
        self.assertIsNone(attr)
        self.assertIn("avatar_marketplace", api_server._SUBSYSTEM_ERRORS)
        api_server._SUBSYSTEM_ERRORS.pop("avatar_marketplace", None)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestCrossUserObjectIsolation(unittest.TestCase):
    """One user must not read or mutate another user's objects by id (BOLA /
    OWASP API1:2023). A systematic sweep of the id-taking endpoints found the
    codebase enforces this uniformly -- handlers pass current_user['user_id']
    into the manager, which scopes the query or raises. These tests lock that
    invariant on a representative endpoint per manager so it can't regress.
    """

    def test_saved_search_delete_is_scoped_to_owner(self):
        from saved_searches import SavedSearchStore
        store = SavedSearchStore()
        a = store.create("userA", "alice's search", "cats")

        with patch.object(api_server, "get_saved_search_store", lambda: store):
            # userB tries to delete userA's saved search by its id.
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.delete_saved_search(a.search_id, {"user_id": "userB"}))
            self.assertEqual(ctx.exception.status_code, 404)
        # It still belongs to A, provable by A being able to delete it.
        self.assertTrue(store.delete("userA", a.search_id))

    def test_notification_mark_read_is_scoped_to_owner(self):
        from user_notifications import NotificationQueue
        q = NotificationQueue()
        n = q.push("userA", "system", "t", "b")

        with patch.object(api_server, "get_notification_queue", lambda: q):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.mark_notification_read(n.notification_id, {"user_id": "userB"}))
            self.assertEqual(ctx.exception.status_code, 404)
        # Still A's and still unread: A can mark it read.
        self.assertTrue(q.mark_read("userA", n.notification_id))

    def test_get_order_passes_the_callers_id_to_the_store(self):
        # A store scoped by user_id can only return the caller's own order iff
        # the handler forwards the caller's id -- assert it does.
        mock_cm = MagicMock()
        mock_cm.get_order.return_value = None
        with patch.object(api_server, "get_cart_manager", lambda: mock_cm):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.get_order("order-owned-by-A", {"user_id": "userB"}))
            self.assertEqual(ctx.exception.status_code, 404)
        mock_cm.get_order.assert_called_once_with("userB", "order-owned-by-A")

    def test_get_commission_rejects_a_non_party(self):
        req = MagicMock()
        req.requester_id = "userA"
        req.creator_id = "creatorC"
        mock_store = MagicMock()
        mock_store.get.return_value = req
        with patch.object(api_server, "get_commission_store", lambda: mock_store):
            # A third user who is neither the requester nor the creator.
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.get_commission("req1", {"user_id": "userD"}))
            self.assertEqual(ctx.exception.status_code, 403)

    def test_get_commission_allows_both_parties(self):
        req = MagicMock()
        req.requester_id = "userA"
        req.creator_id = "creatorC"
        req.to_dict.return_value = {"request_id": "req1"}
        mock_store = MagicMock()
        mock_store.get.return_value = req
        with patch.object(api_server, "get_commission_store", lambda: mock_store):
            for party in ("userA", "creatorC"):
                out = asyncio.run(api_server.get_commission("req1", {"user_id": party}))
                self.assertEqual(out["request_id"], "req1")


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestDirectPurchaseIsRecordedAsAnOrder(unittest.TestCase):
    """A paid purchase must always have an order (FEATURE_AUDIT §3-7).

    Refunds and order history are both keyed by order_id. The direct-download
    path charged the buyer and credited the seller without creating one, so a
    purchase made through the API -- rather than the cart the UI always uses --
    was permanently non-refundable. Recording the order does not change the
    charge; the money has already moved by this point.
    """

    def _listing(self, mkt, price=120):
        return mkt.publish(
            avatar_id="a1", owner_id="seller", owner_username="sel", name="n",
            description="d", tags=[], category="other", parameters={"p": 1},
            price_credits=price, is_free=False,
        )

    def _download(self, mkt, cart, listing, buyer="buyer", promo=""):
        with patch.object(api_server, "get_marketplace", lambda: mkt), \
             patch.object(api_server, "get_cart_manager", lambda: cart), \
             patch.object(api_server, "get_license_manager", None), \
             patch.object(api_server, "get_membership_manager", None), \
             patch.object(api_server, "get_referral_manager", None), \
             patch.object(api_server, "get_notification_queue", None), \
             patch.object(api_server, "get_search_index", None):
            return asyncio.run(api_server.download_avatar(
                listing.listing_id, promo, {"user_id": buyer}))

    def test_paid_direct_download_creates_a_completed_order(self):
        from avatar_marketplace import MarketplaceStore
        from cart_manager import CartManager
        mkt, cart = MarketplaceStore(), CartManager()
        mkt.add_credits("buyer", 500)
        listing = self._listing(mkt)
        self._download(mkt, cart, listing)

        orders = cart.store.get_user_orders("buyer")
        self.assertEqual(orders["total"], 1, "a paid purchase left no order to refund")
        order = orders["items"][0]
        self.assertEqual(order["status"], "completed")
        self.assertEqual(order["total_credits"], 120)
        item = order["items"][0]
        # The clawback on refund reads owner_id/final_price off the item.
        self.assertEqual(item["owner_id"], "seller")
        self.assertEqual(item["final_price"], 120)

    def test_free_download_creates_no_order(self):
        from avatar_marketplace import MarketplaceStore
        from cart_manager import CartManager
        mkt, cart = MarketplaceStore(), CartManager()
        listing = mkt.publish(
            avatar_id="a1", owner_id="seller", owner_username="sel", name="n",
            description="d", tags=[], category="other", parameters={"p": 1},
            price_credits=0, is_free=True,
        )
        self._download(mkt, cart, listing)
        self.assertEqual(cart.store.get_user_orders("buyer")["total"], 0)

    def test_free_redownload_does_not_create_a_second_order(self):
        # Re-downloading something already owned is free, so it must not look
        # like another purchase.
        from avatar_marketplace import MarketplaceStore
        from cart_manager import CartManager
        mkt, cart = MarketplaceStore(), CartManager()
        mkt.add_credits("buyer", 500)
        listing = self._listing(mkt)
        self._download(mkt, cart, listing)
        self._download(mkt, cart, listing)
        self.assertEqual(cart.store.get_user_orders("buyer")["total"], 1)

    def test_bookkeeping_failure_never_costs_the_buyer_their_product(self):
        # The money has already moved; a failure to record must not 500.
        from avatar_marketplace import MarketplaceStore
        mkt = MarketplaceStore()
        mkt.add_credits("buyer", 500)
        listing = self._listing(mkt)
        broken = MagicMock()
        broken.store.create_order.side_effect = RuntimeError("disk on fire")
        out = self._download(mkt, broken, listing)
        self.assertEqual(out["status"], "downloaded")


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestPromisedStateSurvivesACrash(unittest.TestCase):
    """Actions the product CONFIRMED must not be undone by a crash (#84, #85).

    Measured before the fix: register, wait for a snapshot, delete the account
    (200 "deleted", and logging in immediately gives 401), then SIGKILL the
    process before the next 30s tick and restart -- the account logged in
    again with 200. The snapshot still held the user, because deletion only
    removed them from memory.

    This is the #75 pattern, durability resurrecting something deliberately
    destroyed, but worse in kind: the response was a promise that the data no
    longer existed. Ordinary writes may wait for the next tick (a lost
    purchase is visible and repeatable); erasure may not.
    """

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def test_persist_now_writes_without_waiting_for_the_tick(self):
        from avatar_marketplace import MarketplaceStore
        store = MarketplaceStore()
        snapshot = os.path.join(self.state_dir, "state.json")
        with patch.dict(os.environ, {"COCOA_STATE_DIR": self.state_dir}),              patch.object(api_server, "get_marketplace", lambda: store):
            self.assertFalse(os.path.exists(snapshot))
            api_server._persist_now("test")
            self.assertTrue(os.path.exists(snapshot))

    def test_persist_now_is_a_no_op_when_durability_is_off(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COCOA_STATE_DIR", None)
            with patch.object(api_server, "state_snapshot") as mock_snap:
                api_server._persist_now("test")
            mock_snap.save.assert_not_called()

    def test_a_failing_save_never_breaks_the_deletion(self):
        # The account is already gone from memory; the caller must not see an
        # error for it. The failure is surfaced via /ready and the console (#83).
        with patch.dict(os.environ, {"COCOA_STATE_DIR": self.state_dir}),              patch.object(api_server.state_snapshot, "save",
                          side_effect=OSError("No space left on device")):
            api_server._persist_now("test")  # must not raise
        self.assertIs(api_server._last_snapshot["ok"], False)

    def test_every_promise_carrying_handler_persists_immediately(self):
        # Pin the wiring: it is the call site, not the helper, that was missing.
        # Each of these answers with a promise about state that a crash before
        # the next tick would silently take back -- measured for deletion (#84)
        # and for ban (#85, the abusive account logged back in).
        import inspect
        handlers = (
            api_server.delete_own_account,   # "deleted"    (#84)
            api_server.delete_user,          # "deleted"    (#84)
            api_server.ban_user,             # "banned"     (#85)
            api_server.unban_user,           # the reversal (#85)
            api_server.update_moderation_status,  # takedown (#85)
            api_server.admin_restore_listing,     # the reversal (#85)
        )
        for handler in handlers:
            src = inspect.getsource(handler)
            self.assertIn("_persist_now", src,
                          f"{handler.__name__} must force a snapshot: its response "
                          f"promises a state change a crash would otherwise undo")


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestDurabilityHealthIsObservable(unittest.TestCase):
    """A failing snapshot must be visible, not just logged (audit #83).

    #78 fixed saves that crashed; this fixes saves that fail where nobody
    looks. Before: _save_state_best_effort's return value was discarded by the
    autosave loop, so a deployment with a full disk failed every 30 seconds
    forever while /ready said everything was fine and the admin console showed
    nothing. The operator learned the truth at the restart that lost the data.
    """

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(api_server._state_autosave_stop.set)
        # Each test starts from "no attempt yet this process".
        self._orig = dict(api_server._last_snapshot)
        api_server._last_snapshot.update(
            ok=None, at=None, last_success_at=None, error=None, stores=None)
        self.addCleanup(lambda: api_server._last_snapshot.update(self._orig))

    def _ready(self):
        res = asyncio.run(api_server.readiness_probe())
        return res.status_code, json.loads(res.body.decode())

    def test_a_successful_save_is_recorded(self):
        from avatar_marketplace import MarketplaceStore
        store = MarketplaceStore()
        with patch.dict(os.environ, {"COCOA_STATE_DIR": self.state_dir}),              patch.object(api_server, "get_marketplace", lambda: store):
            self.assertTrue(api_server._save_state_best_effort(self.state_dir))
        snap = api_server._last_snapshot
        self.assertIs(snap["ok"], True)
        self.assertIsNotNone(snap["at"])
        self.assertEqual(snap["at"], snap["last_success_at"])
        self.assertIsNone(snap["error"])
        self.assertGreaterEqual(snap["stores"], 1)

    def test_a_failing_save_is_recorded_and_degrades_readiness(self):
        with patch.dict(os.environ, {"COCOA_STATE_DIR": self.state_dir}),              patch.object(api_server.state_snapshot, "save",
                          side_effect=OSError("No space left on device")):
            self.assertFalse(api_server._save_state_best_effort(self.state_dir))
            snap = api_server._last_snapshot
            self.assertIs(snap["ok"], False)
            self.assertIn("No space left", snap["error"])
            status, body = self._ready()
        self.assertEqual(status, 200)  # optional subsystem: degraded, not down
        self.assertEqual(body["status"], "degraded")
        self.assertIn("durability", body["missing_optional"])

    def test_recovery_clears_the_degradation(self):
        from avatar_marketplace import MarketplaceStore
        store = MarketplaceStore()
        with patch.dict(os.environ, {"COCOA_STATE_DIR": self.state_dir}),              patch.object(api_server, "get_marketplace", lambda: store):
            with patch.object(api_server.state_snapshot, "save",
                              side_effect=OSError("boom")):
                api_server._save_state_best_effort(self.state_dir)
            api_server._save_state_best_effort(self.state_dir)  # disk is back
            snap = api_server._last_snapshot
            self.assertIs(snap["ok"], True)
            self.assertIsNone(snap["error"])
            status, body = self._ready()
        self.assertNotIn("durability", body["missing_optional"])

    def test_durability_off_is_healthy_and_visible_as_disabled(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COCOA_STATE_DIR", None)
            # Even a stale failure record must not degrade a process that has
            # durability off (e.g. tests that poked the module state).
            api_server._last_snapshot["ok"] = False
            _, body = self._ready()
            self.assertNotIn("durability", body["missing_optional"])
            with patch.object(api_server, "get_auth_manager", None),                  patch.object(api_server, "get_marketplace", None),                  patch.object(api_server, "get_search_index", None),                  patch.object(api_server, "get_rate_limiter", None):
                stats = asyncio.run(api_server.admin_stats({"user_id": "a", "role": "admin"}))
        self.assertIn("durability", stats)
        self.assertFalse(stats["durability"]["enabled"])

    def test_admin_stats_carries_the_full_record_when_enabled(self):
        from avatar_marketplace import MarketplaceStore
        store = MarketplaceStore()
        with patch.dict(os.environ, {"COCOA_STATE_DIR": self.state_dir}),              patch.object(api_server, "get_marketplace", lambda: store):
            api_server._save_state_best_effort(self.state_dir)
            with patch.object(api_server, "get_auth_manager", None),                  patch.object(api_server, "get_search_index", None),                  patch.object(api_server, "get_rate_limiter", None):
                stats = asyncio.run(api_server.admin_stats({"user_id": "a", "role": "admin"}))
        d = stats["durability"]
        self.assertTrue(d["enabled"])
        self.assertIs(d["ok"], True)
        self.assertIsNotNone(d["last_success_at"])
        self.assertEqual(d["interval_seconds"],
                         api_server._STATE_AUTOSAVE_INTERVAL_SECONDS)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestProportionateEnforcementAndLedgerAudit(unittest.TestCase):
    """Publish quotas and the ledger integrity audit (audit #82).

    Enforcement went straight from taking down one listing (#45) to banning the
    account (#50/#58) with nothing in between, so a seller who floods the
    catalogue but is not ban-worthy had no proportionate response. A publish cap
    is that middle rung, and like every other enforcement action here it has to
    be reversible.

    Neither endpoint had a single test before this.
    """

    def _marketplace(self):
        from avatar_marketplace import MarketplaceStore
        return MarketplaceStore()

    ADMIN = {"user_id": "admin1", "role": "admin"}

    def _publish(self, store, owner, i):
        return store.publish(
            avatar_id=f"a{i}", owner_id=owner, owner_username="s", name=f"n{i}",
            description="d", tags=[], category="other", parameters={"p": i},
        )

    def test_quota_round_trips_through_the_admin_endpoints(self):
        store = self._marketplace()
        self._publish(store, "seller", 0)
        body = api_server.SetQuotaRequest(user_id="seller", max_listings=5)
        with patch.object(api_server, "get_marketplace", lambda: store):
            out = asyncio.run(api_server.set_listing_quota(body, self.ADMIN))
            self.assertEqual(out["max_listings"], 5)
            self.assertEqual(out["current_active"], 1)
            read = asyncio.run(api_server.get_listing_quota("seller", self.ADMIN))
        self.assertEqual(read["max_listings"], 5)
        self.assertEqual(read["current_active"], 1)

    def test_the_cap_actually_blocks_publishing(self):
        # A cap that does not stop anything would be decoration.
        store = self._marketplace()
        body = api_server.SetQuotaRequest(user_id="seller", max_listings=2)
        with patch.object(api_server, "get_marketplace", lambda: store):
            asyncio.run(api_server.set_listing_quota(body, self.ADMIN))
        self._publish(store, "seller", 0)
        self._publish(store, "seller", 1)
        with self.assertRaises(ValueError):
            self._publish(store, "seller", 2)

    def test_minus_one_lifts_the_cap_again(self):
        # Reversibility is the point (#45, #58): enforcement you cannot undo is
        # a trap for the operator, not a tool.
        store = self._marketplace()
        with patch.object(api_server, "get_marketplace", lambda: store):
            asyncio.run(api_server.set_listing_quota(
                api_server.SetQuotaRequest(user_id="seller", max_listings=1), self.ADMIN))
            self._publish(store, "seller", 0)
            with self.assertRaises(ValueError):
                self._publish(store, "seller", 1)
            out = asyncio.run(api_server.set_listing_quota(
                api_server.SetQuotaRequest(user_id="seller", max_listings=-1), self.ADMIN))
            self.assertIsNone(out["max_listings"])
            self.assertEqual(out["status"], "unlimited")
        self._publish(store, "seller", 1)  # must not raise any more
        self.assertEqual(len(store.get_user_listings("seller")), 2)

    def test_ledger_audit_reports_a_sound_ledger(self):
        store = self._marketplace()
        store.add_credits("alice", 100)
        with patch.object(api_server, "get_marketplace", lambda: store):
            out = asyncio.run(api_server.credit_ledger_integrity(self.ADMIN))
        self.assertTrue(out["consistent"])
        self.assertEqual(out["discrepancy_count"], 0)
        self.assertGreaterEqual(out["users_checked"], 1)

    def test_ledger_audit_catches_a_balance_that_bypassed_the_primitives(self):
        # This is the same invariant a restored snapshot is verified against
        # (#71) and that the concurrency tests assert (#81); the endpoint is how
        # an operator sees it live.
        store = self._marketplace()
        store.add_credits("alice", 100)
        store._credits["alice"] = 999  # a write that skipped the ledger
        with patch.object(api_server, "get_marketplace", lambda: store):
            out = asyncio.run(api_server.credit_ledger_integrity(self.ADMIN))
        self.assertFalse(out["consistent"])
        self.assertEqual(out["discrepancy_count"], 1)
        self.assertEqual(out["discrepancies"][0]["user_id"], "alice")


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestRoleChangeHandlerStatusCodes(unittest.TestCase):
    """The role endpoint must not report "forbidden" as "bad request".

    get_current_admin admits admin AND moderator, so a moderator reaches the
    handler and is stopped by change_role's own require_role("admin"). The
    handler used to collapse AuthError and ValueError into a single 400, so
    that refusal looked like a malformed request. verify_creator, which has the
    identical double gate, already mapped it to 403 -- this aligns them.
    """

    def _auth(self):
        from auth_manager import AuthManager, UserStore
        return AuthManager(store=UserStore())

    def _payload(self, auth, username, password="Sup3rSecret!"):
        return auth.verify_access_token(auth.login(username, password).access_token)

    def _call(self, auth, actor, target_id, new_role):
        body = api_server.RoleChangeRequest(new_role=new_role)
        with patch.object(api_server, "get_auth_manager", lambda: auth):
            return asyncio.run(api_server.change_user_role(target_id, body, actor))

    def test_moderator_gets_403_not_400(self):
        auth = self._auth()
        auth.register("boss", "boss@x.com", "Sup3rSecret!", role="admin")
        mod = auth.register("mod", "mod@x.com", "Sup3rSecret!", role="moderator")
        victim = auth.register("bob", "bob@x.com", "Sup3rSecret!")
        with self.assertRaises(HTTPException) as ctx:
            self._call(auth, self._payload(auth, "mod"), victim.user_id, "admin")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(auth.store.get_by_id(victim.user_id).role, "user")
        self.assertEqual(mod.role, "moderator")

    def test_self_demotion_gets_403(self):
        auth = self._auth()
        admin = auth.register("boss", "boss@x.com", "Sup3rSecret!", role="admin")
        with self.assertRaises(HTTPException) as ctx:
            self._call(auth, self._payload(auth, "boss"), admin.user_id, "user")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(auth.store.get_by_id(admin.user_id).role, "admin")

    def test_unknown_user_gets_404(self):
        auth = self._auth()
        auth.register("boss", "boss@x.com", "Sup3rSecret!", role="admin")
        with self.assertRaises(HTTPException) as ctx:
            self._call(auth, self._payload(auth, "boss"), "no-such-user", "moderator")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_unknown_role_is_still_400(self):
        auth = self._auth()
        auth.register("boss", "boss@x.com", "Sup3rSecret!", role="admin")
        victim = auth.register("bob", "bob@x.com", "Sup3rSecret!")
        with self.assertRaises(HTTPException) as ctx:
            self._call(auth, self._payload(auth, "boss"), victim.user_id, "superuser")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_promoting_another_account_still_succeeds(self):
        auth = self._auth()
        auth.register("boss", "boss@x.com", "Sup3rSecret!", role="admin")
        victim = auth.register("bob", "bob@x.com", "Sup3rSecret!")
        out = self._call(auth, self._payload(auth, "boss"), victim.user_id, "moderator")
        self.assertEqual(out["status"], "updated")
        self.assertEqual(auth.store.get_by_id(victim.user_id).role, "moderator")

    def test_roster_exposes_creator_badge_state(self):
        # The console needs this to offer revocation only where a badge exists.
        auth = self._auth()
        auth.register("boss", "boss@x.com", "Sup3rSecret!", role="admin")
        with patch.object(api_server, "get_auth_manager", lambda: auth):
            out = asyncio.run(api_server.list_users({"user_id": "x", "role": "admin"}))
        self.assertIn("is_creator_verified", out["users"][0])


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestOptInStatePersistence(unittest.TestCase):
    """Wiring for COCOA_STATE_DIR (audit #71).

    MarketplaceStore has carried a complete, integrity-verified credit-state
    persistence API with zero callers; UserStore gained the mirror-image API
    because money alone is incoherent (balances are keyed by user_id, so
    restoring them without accounts leaves orphaned money nobody can claim).
    These tests pin the server wiring: off by default, load at startup, save at
    shutdown, and fail-closed on a corrupt snapshot -- silently starting with
    zeroed balances or an empty user table would be the money version of the
    #47 anti-pattern.
    """

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)
        # The autosave thread from a previous test must not leak.
        self.addCleanup(api_server._state_autosave_stop.set)

    def _fresh_marketplace(self):
        from avatar_marketplace import MarketplaceStore
        return MarketplaceStore()

    def _fresh_auth(self):
        from auth_manager import AuthManager, UserStore
        return AuthManager(store=UserStore())

    def _run_startup(self, auth, mkt):
        with patch.dict(os.environ, {"COCOA_STATE_DIR": self.state_dir}), \
             patch.object(api_server, "get_auth_manager", lambda: auth), \
             patch.object(api_server, "get_marketplace", lambda: mkt):
            asyncio.run(api_server._load_persisted_state())

    def _run_shutdown(self, auth, mkt):
        with patch.dict(os.environ, {"COCOA_STATE_DIR": self.state_dir}), \
             patch.object(api_server, "get_auth_manager", lambda: auth), \
             patch.object(api_server, "get_marketplace", lambda: mkt):
            asyncio.run(api_server._save_persisted_state())

    def test_unset_env_is_a_no_op(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COCOA_STATE_DIR", None)
            mkt = MagicMock()
            auth = MagicMock()
            with patch.object(api_server, "get_marketplace", lambda: mkt), \
                 patch.object(api_server, "get_auth_manager", lambda: auth):
                asyncio.run(api_server._load_persisted_state())
                asyncio.run(api_server._save_persisted_state())
        mkt.load_credit_state.assert_not_called()
        mkt.save_credit_state.assert_not_called()
        auth.store.load_user_state.assert_not_called()
        auth.store.save_user_state.assert_not_called()

    def test_accounts_and_money_survive_a_simulated_restart(self):
        auth = self._fresh_auth()
        mkt = self._fresh_marketplace()
        user = auth.register("alice", "alice@example.com", "Sup3rSecret!")
        mkt.add_credits(user.user_id, 250)
        self._run_shutdown(auth, mkt)

        # Brand-new stores = a restarted process.
        auth2 = self._fresh_auth()
        mkt2 = self._fresh_marketplace()
        self._run_startup(auth2, mkt2)
        # The same person can still LOG IN (identity survived) ...
        tokens = auth2.login("alice", "Sup3rSecret!")
        self.assertTrue(tokens.access_token)
        # ... and their money is still theirs.
        self.assertEqual(mkt2.get_balance(user.user_id), 250)

    def test_missing_snapshot_starts_fresh(self):
        auth = self._fresh_auth()
        mkt = self._fresh_marketplace()
        self._run_startup(auth, mkt)  # must not raise
        self.assertEqual(mkt.get_balance("nobody"), 0)

    def test_corrupt_credit_snapshot_refuses_to_start(self):
        # Balances that do not match their ledger must still be refused after
        # the generic codec restores them (#71's guarantee, re-applied in #74).
        path = os.path.join(self.state_dir, "state.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "stores": {
                "marketplace": {"_credits": {"alice": 999}, "_credit_ledger": {}}}}, f)
        mkt = self._fresh_marketplace()
        with self.assertRaises(ValueError):
            self._run_startup(self._fresh_auth(), mkt)

    def test_corrupt_user_snapshot_refuses_to_start(self):
        path = os.path.join(self.state_dir, "state.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "stores": {"users": {"_by_id": {
                "u1": {"__t__": "dc", "n": "NoSuchClass", "v": {}}}}}}, f)
        with self.assertRaises(Exception):
            self._run_startup(self._fresh_auth(), self._fresh_marketplace())

    def test_password_hashes_never_leave_the_snapshot_worldreadable(self):
        auth = self._fresh_auth()
        auth.register("bob", "bob@example.com", "Sup3rSecret!")
        self._run_shutdown(auth, self._fresh_marketplace())
        mode = os.stat(os.path.join(self.state_dir, "state.json")).st_mode & 0o777
        self.assertEqual(mode & 0o077, 0, f"snapshot mode {oct(mode)} is group/world accessible")

    def test_startup_arms_the_autosave_thread(self):
        auth = self._fresh_auth()
        mkt = self._fresh_marketplace()
        self._run_startup(auth, mkt)
        thread = api_server._state_autosave_thread
        self.assertIsNotNone(thread)
        self.assertTrue(thread.is_alive())
        self._run_shutdown(auth, mkt)
        self.assertFalse(thread.is_alive())


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestFeedEndpointsDoNotFakeAnEmptyResult(unittest.TestCase):
    """Stragglers from #47: an outage must not look like "nothing to show".

    #47 converted 52 endpoints from an empty 200 to a 503, but three kept the
    old shape -- and one of them, /api/auth/feed, is what the Feed page calls.
    With auth or marketplace down, a user was told the creators they follow had
    published nothing, which is indistinguishable from the truth.

    The genuinely-empty answers must survive: following nobody really is an
    empty feed, and that still returns 200.
    """

    ENDPOINTS = (
        ("creator_feed", lambda: api_server.creator_feed(20, 0, {"user_id": "u1"})),
        ("get_tag_feed", lambda: api_server.get_tag_feed(20, 0, "newest", {"user_id": "u1"})),
        ("list_favorites", lambda: api_server.list_favorites({"user_id": "u1"})),
    )

    def test_503_when_a_required_subsystem_is_missing(self):
        for name, call in self.ENDPOINTS:
            for missing in ("get_auth_manager", "get_marketplace"):
                with self.subTest(endpoint=name, missing=missing):
                    with patch.object(api_server, missing, None):
                        with self.assertRaises(HTTPException) as ctx:
                            asyncio.run(call())
                    self.assertEqual(ctx.exception.status_code, 503)

    def test_following_nobody_is_still_an_honest_empty_feed(self):
        # The real empty case must NOT have been turned into an error.
        auth = MagicMock()
        auth.get_following.return_value = []
        with patch.object(api_server, "get_auth_manager", lambda: auth), \
             patch.object(api_server, "get_marketplace", lambda: MagicMock()):
            out = asyncio.run(api_server.creator_feed(20, 0, {"user_id": "u1"}))
        self.assertEqual(out["total"], 0)
        self.assertEqual(out["items"], [])


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestAvatarEndpointsReportMissingDatabaseHonestly(unittest.TestCase):
    """A deployment without SQLAlchemy must say so, not lie in three directions.

    database_manager imports cleanly without SQLAlchemy but every session call
    then dies on `NameError: sessionmaker`. That produced three different
    dishonest answers on the /api/avatars family:
      GET  /api/avatars/{id} -> 500 (a config state reported as a server bug)
      GET  /api/avatars      -> 200 {"avatars": [], "status": "success"}
                                (outage indistinguishable from an empty list --
                                 the anti-pattern #47 removed from 52 endpoints)
      POST /api/avatars      -> 200 {"status": "created_mock"} with a fresh uuid
                                (a WRITE reporting success for data never saved)
    All three must be 503, per the convention #47 established.
    """

    CALLS = (
        ("get_avatars", lambda: api_server.get_avatars({"user_id": "u1"})),
        ("get_avatar", lambda: api_server.get_avatar("any-id", {"user_id": "u1"})),
        ("create_avatar", lambda: api_server.create_avatar({"name": "X"}, {"user_id": "u1"})),
    )

    def test_all_avatar_endpoints_503_when_sqlalchemy_is_absent(self):
        with patch.object(api_server, "SQLALCHEMY_AVAILABLE", False):
            for name, call in self.CALLS:
                with self.subTest(endpoint=name):
                    with self.assertRaises(HTTPException) as ctx:
                        asyncio.run(call())
                    self.assertEqual(ctx.exception.status_code, 503)
                    self.assertIn("データベース", ctx.exception.detail)

    def test_listing_avatars_never_reports_an_empty_success(self):
        # The specific regression: a broken database must not look like "you
        # simply have no avatars", and must never claim status=success.
        with patch.object(api_server, "SQLALCHEMY_AVAILABLE", False):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.get_avatars({"user_id": "u1"}))
        self.assertNotEqual(ctx.exception.status_code, 200)

    def test_create_avatar_never_fabricates_a_created_id(self):
        # A write that cannot be durable must fail rather than hand back an id
        # that resolves to nothing.
        with patch.object(api_server, "SQLALCHEMY_AVAILABLE", False):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.create_avatar({"name": "X"}, {"user_id": "u1"}))
        self.assertEqual(ctx.exception.status_code, 503)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestAdminPayloadShapeIsNotCrossed(unittest.TestCase):
    """Two admin payload shapes coexist and must not be confused.

    get_current_user/get_current_admin return the NORMALIZED dict
    ({"user_id", "username", "role"}) while _verify_token returns the RAW JWT
    ({"sub", ...}). Reading "sub" off a normalized payload raised KeyError ->
    HTTP 500 on POST /api/admin/licenses/{key_id}/revoke, making admin
    revocation unreachable (a key's holder gets 403 from the owner-only route,
    so the admin path was the only one). FEATURE_AUDIT.md #49 was the same
    mismatch in auth_manager; this pins both the fix and the whole class.
    """

    def test_admin_license_revoke_passes_the_admins_id(self):
        mock_lm = MagicMock()
        mock_lm.revoke_key.return_value = {"key_id": "k1", "is_revoked": True}
        body = api_server.RevokeLicenseRequest(reason="規約違反")
        with patch.object(api_server, "get_license_manager", lambda: mock_lm):
            out = asyncio.run(
                api_server.admin_revoke_license(
                    "k1", body, {"user_id": "admin-1", "username": "adm", "role": "admin"}
                )
            )
        self.assertTrue(out["is_revoked"])
        # The revoker id must be the admin's real id, not "" and not a KeyError.
        mock_lm.revoke_key.assert_called_once_with("k1", "admin-1", "規約違反", is_admin=True)

    def test_no_endpoint_reads_sub_off_a_normalized_payload(self):
        """Class-level guard: statically reject the mismatch anywhere in the app.

        Any handler parameter defaulted to Depends(get_current_user/admin) holds
        the normalized dict, so `param["sub"]` / `param.get("sub")` inside that
        handler is always wrong. Endpoints that legitimately need the raw JWT
        call _verify_token() and bind it to a local, which this does not flag.
        """
        import ast
        from pathlib import Path

        source_path = Path(api_server.__file__)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        dep_funcs = {"get_current_user", "get_current_admin"}

        def dependency_of(default):
            if isinstance(default, ast.Call) and getattr(default.func, "id", None) == "Depends":
                if default.args:
                    name = getattr(default.args[0], "id", None)
                    if name in dep_funcs:
                        return name
            return None

        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            spec = node.args
            normalized = {}
            if spec.defaults:
                for arg, default in zip(spec.args[len(spec.args) - len(spec.defaults):], spec.defaults):
                    dep = dependency_of(default)
                    if dep:
                        normalized[arg.arg] = dep
            for arg, default in zip(spec.kwonlyargs, spec.kw_defaults):
                if default is None:
                    continue
                dep = dependency_of(default)
                if dep:
                    normalized[arg.arg] = dep
            if not normalized:
                continue
            for inner in ast.walk(node):
                base = key = None
                if isinstance(inner, ast.Subscript):
                    base = getattr(inner.value, "id", None)
                    key = getattr(inner.slice, "value", None)
                elif isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) \
                        and inner.func.attr == "get" and inner.args:
                    base = getattr(inner.func.value, "id", None)
                    key = getattr(inner.args[0], "value", None)
                if base in normalized and key == "sub":
                    offenders.append(f"{node.name}() at line {inner.lineno}")

        self.assertEqual(
            offenders, [],
            "These handlers read 'sub' from a normalized payload (use 'user_id'): "
            + ", ".join(offenders),
        )


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestReporterOutcomeNotification(unittest.TestCase):
    """Resolving a report must close the loop with the reporter.

    A filed report deserves an outcome acknowledgement (moderation guidance:
    builds reporter trust, cuts repeat reports). The notification must expose
    only the outcome category -- never the internal resolution_note, and never
    what enforcement hit the reported party -- and must not fire when the
    reporter resolved their own report.
    """

    def _make_marketplace(self, reporter_id="reporterX", note="内部メモ: 明白な規約違反"):
        from unittest.mock import MagicMock
        mkt = MagicMock()
        report = MagicMock()
        report.reporter_id = reporter_id
        report.report_id = "rep1"
        report.listing_id = "L1"
        report.reason = "malware"
        report.resolution_note = note
        report.to_dict.return_value = {"report_id": "rep1"}
        mkt.resolve_report.return_value = report
        listing = MagicMock()
        listing.name = "悪意ある服"
        mkt.get_listing.return_value = listing
        return mkt

    def _resolve(self, action, reporter_id="reporterX", moderator="modA", note="内部メモ: 明白な規約違反"):
        from user_notifications import NotificationQueue
        q = NotificationQueue()
        mkt = self._make_marketplace(reporter_id=reporter_id, note=note)
        body = api_server.ResolveReportRequest(action=action, note=note, takedown=False)
        with patch.object(api_server, "get_marketplace", lambda: mkt), \
             patch.object(api_server, "get_notification_queue", lambda: q), \
             patch.object(api_server, "get_moderation_queue", None), \
             patch.object(api_server, "get_search_index", None):
            asyncio.run(api_server.resolve_report("rep1", body, {"user_id": moderator}))
        return q.get_notifications(reporter_id)["items"]

    def test_resolved_notifies_reporter_action_taken(self):
        items = self._resolve("resolved")
        self.assertEqual(len(items), 1)
        n = items[0]
        self.assertEqual(n["kind"], "report_reviewed")
        self.assertIn("対応しました", n["title"] + n["body"])
        self.assertIn("悪意ある服", n["body"])  # subject name surfaced
        self.assertEqual(n["payload"]["outcome"], "resolved")

    def test_dismissed_notifies_reporter_no_violation(self):
        items = self._resolve("dismissed")
        self.assertEqual(len(items), 1)
        self.assertIn("違反は確認されませんでした", items[0]["body"])

    def test_internal_note_is_never_leaked_to_reporter(self):
        # The resolution_note is an internal handoff record (#46); it must not
        # reach the person who filed the report.
        for action in ("resolved", "dismissed"):
            items = self._resolve(action, note="内部メモ: 通報者には見せない")
            blob = items[0]["title"] + items[0]["body"] + json.dumps(items[0]["payload"], ensure_ascii=False)
            self.assertNotIn("内部メモ", blob)
            self.assertNotIn("見せない", blob)

    def test_self_report_does_not_notify(self):
        # Reporter and moderator are the same account -> no self-notification.
        items = self._resolve("resolved", reporter_id="modA", moderator="modA")
        self.assertEqual(items, [])

    def test_muting_report_reviewed_suppresses_the_notice(self):
        from user_notifications import NotificationQueue
        q = NotificationQueue()
        q.mute_kind("reporterX", "report_reviewed")
        mkt = self._make_marketplace()
        body = api_server.ResolveReportRequest(action="resolved", note="x", takedown=False)
        with patch.object(api_server, "get_marketplace", lambda: mkt), \
             patch.object(api_server, "get_notification_queue", lambda: q), \
             patch.object(api_server, "get_moderation_queue", None), \
             patch.object(api_server, "get_search_index", None):
            asyncio.run(api_server.resolve_report("rep1", body, {"user_id": "modA"}))
        self.assertEqual(q.get_notifications("reporterX")["items"], [])

    def test_review_report_resolution_notifies_with_review_fallback(self):
        from user_notifications import NotificationQueue
        from unittest.mock import MagicMock
        q = NotificationQueue()
        mkt = MagicMock()
        report = MagicMock()
        report.reporter_id = "reviewReporter"
        report.report_id = "rr1"
        report.to_dict.return_value = {"report_id": "rr1"}
        mkt.resolve_review_report.return_value = report
        body = api_server.ResolveReviewReportRequest(action="resolved", note="内部メモ", hide=False)
        with patch.object(api_server, "get_marketplace", lambda: mkt), \
             patch.object(api_server, "get_notification_queue", lambda: q), \
             patch.object(api_server, "get_moderation_queue", None):
            asyncio.run(api_server.resolve_review_report("rr1", body, {"user_id": "modB"}))
        items = q.get_notifications("reviewReporter")["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["kind"], "report_reviewed")
        self.assertIn("レビュー", items[0]["body"])  # review fallback label
        self.assertNotIn("内部メモ", items[0]["body"])


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestOperationalEndpointsRequireAdmin(unittest.TestCase):
    """Operational endpoints must not be readable by ordinary users.

    /metrics (JSON), /backups and /security/report expose system-level
    information -- performance, backup inventory, threat posture -- and were
    gated only by get_current_user, so any logged-in account could read them
    (OWASP API5:2023 Broken Function Level Authorization). They now require the
    admin/moderator role. (The Prometheus scrape target is the separate,
    intentionally unauthenticated GET /metrics/prometheus, so gating the JSON
    endpoint does not affect monitoring.)
    """

    OPERATIONAL_PATHS = ("/metrics", "/backups", "/security/report")

    @staticmethod
    def _dependency_calls(route):
        """Every callable in a route's resolved dependency tree."""
        seen = []

        def walk(dependant):
            for dep in dependant.dependencies:
                if dep.call is not None:
                    seen.append(dep.call)
                walk(dep)

        walk(route.dependant)
        return seen

    def _route(self, path):
        for route in api_server.app.routes:
            if getattr(route, "path", None) == path:
                return route
        self.fail(f"route {path} not found")

    def test_admin_dependency_is_wired_on_each_endpoint(self):
        for path in self.OPERATIONAL_PATHS:
            with self.subTest(path=path):
                calls = self._dependency_calls(self._route(path))
                self.assertIn(
                    api_server.get_current_admin, calls,
                    f"{path} must depend on get_current_admin",
                )

    def test_a_public_endpoint_is_not_admin_gated(self):
        # Guards against the introspection above trivially passing everywhere:
        # /live is a liveness probe and must stay open.
        calls = self._dependency_calls(self._route("/live"))
        self.assertNotIn(api_server.get_current_admin, calls)

    def test_admin_gate_rejects_a_normal_user(self):
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(api_server.get_current_admin({"user_id": "u1", "role": "user"}))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_admin_gate_admits_admin_and_moderator(self):
        for role in ("admin", "moderator"):
            with self.subTest(role=role):
                out = asyncio.run(api_server.get_current_admin({"user_id": "u1", "role": role}))
                self.assertEqual(out["role"], role)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestOperationalEndpointsReportUnavailability(unittest.TestCase):
    """When the backing subsystem is absent, these endpoints must say so (503)
    rather than manufacture a reassuring stub.

    A "threat_level: low" security report or an empty "status: ok" metrics
    report tells an operator everything is fine when monitoring is not even
    running -- the same silent-degradation trap as #47/#53.
    """

    ADMIN = {"user_id": "admin1", "role": "admin"}

    def test_backups_503_when_recovery_subsystem_absent(self):
        with patch.object(api_server, "get_recovery_manager", None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.list_backups(self.ADMIN))
        self.assertEqual(ctx.exception.status_code, 503)

    def test_security_report_503_instead_of_false_all_clear(self):
        with patch.object(api_server, "get_security_manager", None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.get_security_report(self.ADMIN))
        self.assertEqual(ctx.exception.status_code, 503)

    def test_metrics_503_instead_of_empty_ok(self):
        with patch.object(api_server, "PerformanceMonitor", None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.get_metrics(self.ADMIN))
        self.assertEqual(ctx.exception.status_code, 503)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestTwoFactorUnconfiguredIsNotAServerError(unittest.TestCase):
    """An unconfigured optional feature is not a server fault.

    TwoFactorAuthService raises by design when COCOA_2FA_SECRET is unset (it
    refuses to encrypt TOTP seeds under a shared default key). Every /api/2fa/*
    handler caught that RuntimeError and returned 500, so simply opening the
    security page emitted server errors -- polluting the 5xx metrics the
    Prometheus instrumentation records and hiding real faults. 500 means "the
    server hit an unexpected condition"; "this deployment has no 2FA" is a
    known configuration state, which is what 501 is for.
    """

    def setUp(self):
        self._env = patch.dict(os.environ, {}, clear=False)
        self._env.start()
        os.environ.pop("COCOA_2FA_SECRET", None)
        # Reset the singleton so the missing secret is re-evaluated.
        import two_factor_auth as tfa
        self._tfa = tfa
        self._saved = tfa._two_factor_service
        tfa._two_factor_service = None

    def tearDown(self):
        self._tfa._two_factor_service = self._saved
        self._env.stop()

    def test_availability_probe_reports_false(self):
        self.assertFalse(api_server._two_factor_available())

    def test_status_answers_200_with_available_false(self):
        """The honest answer to "is my 2FA on?" is "no, and it isn't offered
        here" -- an answer, not an error."""
        result = asyncio.run(api_server.get_two_factor_status({"user_id": "u1"}))
        self.assertIs(result["available"], False)
        self.assertIs(result["status"]["is_enabled"], False)

    def test_status_does_not_raise(self):
        # This is the call the security page makes on every load.
        try:
            asyncio.run(api_server.get_two_factor_status({"user_id": "u1"}))
        except HTTPException as exc:  # pragma: no cover - failure path
            self.fail(f"status raised {exc.status_code} for an unconfigured deployment")

    def test_mutating_endpoints_return_501_not_500(self):
        user = {"user_id": "u1"}
        calls = {
            "setup": lambda: api_server.setup_two_factor_auth("alice", user),
            "enable": lambda: api_server.enable_two_factor_auth("alice", "123456", user),
            "verify": lambda: api_server.verify_two_factor_token("123456", user),
            "verify-backup": lambda: api_server.verify_two_factor_backup_code("code", user),
            "disable": lambda: api_server.disable_two_factor_auth("pw", user),
        }
        for name, call in calls.items():
            with self.subTest(endpoint=name):
                with self.assertRaises(HTTPException) as ctx:
                    asyncio.run(call())
                self.assertEqual(ctx.exception.status_code, 501)
                self.assertIn("2要素認証", ctx.exception.detail)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestTwoFactorConfiguredStillWorks(unittest.TestCase):
    """The 501 guard must not shadow a properly configured deployment."""

    def setUp(self):
        self._env = patch.dict(os.environ, {"COCOA_2FA_SECRET": "a-test-secret-value"})
        self._env.start()
        import two_factor_auth as tfa
        self._tfa = tfa
        self._saved = tfa._two_factor_service
        tfa._two_factor_service = None
        # Same harness artifact TestLegacyTwoFactorEndpoints documents: this
        # file bare-imports api_server, so its relative 2FA imports fell back
        # to None. Patch in the real callables to exercise a genuinely
        # configured deployment.
        for name in ("get_two_factor_service", "get_2fa_status", "setup_2fa"):
            patcher = patch.object(api_server, name, getattr(tfa, name))
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self._tfa._two_factor_service = self._saved
        self._env.stop()

    def test_availability_probe_reports_true(self):
        self.assertTrue(api_server._two_factor_available())

    def test_status_reports_available_and_real_state(self):
        result = asyncio.run(api_server.get_two_factor_status({"user_id": "u_2fa_cfg"}))
        self.assertIs(result["available"], True)
        # A brand-new user has 2FA off, but the answer comes from the service.
        self.assertIn("status", result)

    def test_setup_is_not_blocked(self):
        result = asyncio.run(api_server.setup_two_factor_auth("alice2fa", {"user_id": "u_2fa_cfg2"}))
        self.assertEqual(result["status"], "success")


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestReadinessProbe(unittest.TestCase):
    """/ready must distinguish 'critical dependency down' (503) from
    'a feature is missing but the site serves' (200 + degraded)."""

    @staticmethod
    def _run():
        res = asyncio.run(api_server.readiness_probe())
        return res.status_code, json.loads(res.body.decode())

    def test_reports_ready_when_all_present(self):
        # 2FA counts as an optional subsystem and is probed for real (a missing
        # COCOA_2FA_SECRET is a construction failure no import check can see),
        # so "all present" only holds when 2FA is genuinely usable. In this
        # harness the 2FA import itself falls back to None, so stand in a
        # working service the way TestLegacyTwoFactorEndpoints does.
        with patch.object(api_server, "get_two_factor_service", lambda: object()):
            code, body = self._run()
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "ready")
        self.assertEqual(body["missing_critical"], [])

    def test_unconfigured_two_factor_is_degraded_not_down(self):
        """An unconfigured optional feature must not take the app out of
        rotation, but an operator should still see it without reading logs."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COCOA_2FA_SECRET", None)
            code, body = self._run()
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "degraded")
        self.assertIn("two_factor", body["missing_optional"])
        self.assertEqual(body["missing_critical"], [])

    def test_missing_critical_subsystem_fails_readiness(self):
        with patch.object(api_server, "get_marketplace", None):
            code, body = self._run()
        self.assertEqual(code, 503)
        self.assertEqual(body["status"], "not_ready")
        self.assertIn("marketplace", body["missing_critical"])

    def test_missing_optional_subsystem_reports_degraded_not_down(self):
        with patch.object(api_server, "get_wishlist_manager", None):
            code, body = self._run()
        # Still serving -- an absent wishlist must not take the site out of
        # rotation the way a missing marketplace does.
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "degraded")
        self.assertIn("wishlist", body["missing_optional"])
        self.assertEqual(body["missing_critical"], [])


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestUnavailableSubsystemIsNotSilentlyEmpty(unittest.TestCase):
    """A missing dependency must surface as 503, not as an empty 200.

    Returning `{"items": []}` when the marketplace is unavailable is
    indistinguishable from "there are genuinely no listings", so an outage
    looked like an empty catalogue.
    """

    def test_browse_raises_503_instead_of_returning_empty(self):
        with patch.object(api_server, "get_marketplace", None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.browse_marketplace())
        self.assertEqual(ctx.exception.status_code, 503)

    def test_notifications_raise_503_instead_of_returning_empty(self):
        with patch.object(api_server, "get_notification_queue", None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(api_server.unread_notification_count({"user_id": "u1"}))
        self.assertEqual(ctx.exception.status_code, 503)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi/pydantic not installed")
class TestHealthEndpointStatusMapping(unittest.TestCase):
    """Regression: GET /health could never report healthy.

    health_check() compared run_all_checks()["status"] against the literal
    "ok", but HealthMonitor only ever emits HealthStatus values
    ("healthy"/"degraded"/"unhealthy"/"critical"). The comparison therefore
    never matched and the endpoint answered "unhealthy" on a perfectly
    healthy system -- making the probe useless for orchestrators.
    """

    def _status_for(self, monitor_status):
        fake_monitor = MagicMock()
        fake_monitor.run_all_checks.return_value = {"status": monitor_status}
        with patch.object(api_server, "get_health_monitor", lambda: fake_monitor):
            result = asyncio.run(api_server.health_check())
        return result.status

    def test_healthy_monitor_reports_healthy(self):
        self.assertEqual(self._status_for("healthy"), "healthy")

    def test_degraded_is_surfaced_not_flattened(self):
        self.assertEqual(self._status_for("degraded"), "degraded")

    def test_unhealthy_is_propagated(self):
        self.assertEqual(self._status_for("unhealthy"), "unhealthy")

    def test_critical_is_propagated(self):
        self.assertEqual(self._status_for("critical"), "critical")

    def test_missing_status_falls_back_to_unhealthy(self):
        self.assertEqual(self._status_for(None), "unhealthy")


if __name__ == "__main__":
    unittest.main()
