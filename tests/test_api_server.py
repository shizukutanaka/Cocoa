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

    def _body(self, username="alice", email="alice@example.com", password="hunter22"):
        body = MagicMock()
        body.username = username
        body.email = email
        body.password = password
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


if __name__ == "__main__":
    unittest.main()
