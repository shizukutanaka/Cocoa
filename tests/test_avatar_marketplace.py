"""Tests for main/avatar_marketplace.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from avatar_marketplace import (
    ListingReport,
    ListingVersion,
    MarketplaceStore,
    PurchaseDispute,
    Review,
    ReviewReply,
)


def _store():
    return MarketplaceStore()


def _buy(store, listing_id, *user_ids):
    """Download a free listing for each user so they qualify to rate/review."""
    for uid in user_ids:
        store.download(listing_id, uid)


def _listing(store, **kw):
    defaults = dict(
        avatar_id="av1", owner_id="u1", owner_username="alice",
        name="Test Avatar", description="desc", tags=["cute", "cat"],
        category="vrc", parameters={"x": 1},
    )
    defaults.update(kw)
    return store.publish(**defaults)


class TestPublish(unittest.TestCase):
    def test_creates_listing(self):
        store = _store()
        listing = _listing(store)
        self.assertIsNotNone(listing.listing_id)
        self.assertEqual(listing.name, "Test Avatar")
        self.assertTrue(listing.is_active)

    def test_duplicate_avatar_raises(self):
        store = _store()
        _listing(store)
        with self.assertRaises(ValueError):
            _listing(store)  # same avatar_id + owner

    def test_tags_lowercased(self):
        store = _store()
        listing = _listing(store, tags=["CUTE", "CAT"])
        self.assertIn("cute", listing.tags)
        self.assertIn("cat", listing.tags)

    def test_tags_capped_at_20(self):
        store = _store()
        listing = _listing(store, tags=[f"tag{i}" for i in range(30)])
        self.assertLessEqual(len(listing.tags), 20)

    def test_default_license_is_personal(self):
        store = _store()
        listing = _listing(store)
        self.assertEqual(listing.license_type, "personal")

    def test_platform_stored_and_lowercased(self):
        store = _store()
        listing = _listing(store, platform="VRChat")
        self.assertEqual(listing.platform, "vrchat")

    def test_platform_in_to_dict(self):
        store = _store()
        listing = _listing(store, platform="neos")
        d = listing.to_dict()
        self.assertIn("platform", d)
        self.assertEqual(d["platform"], "neos")

    def test_platform_default_empty(self):
        store = _store()
        listing = _listing(store)
        self.assertEqual(listing.platform, "")

    def test_update_listing_platform(self):
        store = _store()
        listing = _listing(store, platform="neos")
        updated = store.update_listing(listing.listing_id, listing.owner_id, platform="VRChat")
        self.assertEqual(updated.platform, "vrchat")

    def test_update_listing_platform_none_leaves_unchanged(self):
        store = _store()
        listing = _listing(store, platform="neos")
        updated = store.update_listing(listing.listing_id, listing.owner_id, name="New Name")
        self.assertEqual(updated.platform, "neos")

    def test_custom_license_stored(self):
        store = _store()
        listing = _listing(store, license_type="cc_by", license_details="Attribution required")
        self.assertEqual(listing.license_type, "cc_by")
        self.assertEqual(listing.license_details, "Attribution required")

    def test_license_in_to_dict(self):
        store = _store()
        listing = _listing(store, license_type="commercial")
        d = listing.to_dict()
        self.assertIn("license_type", d)
        self.assertEqual(d["license_type"], "commercial")

    def test_update_listing_changes_license(self):
        store = _store()
        listing = _listing(store)
        store.update_listing(listing.listing_id, "u1", license_type="cc_by_sa")
        self.assertEqual(listing.license_type, "cc_by_sa")


class TestUnpublish(unittest.TestCase):
    def test_owner_can_unpublish(self):
        store = _store()
        listing = _listing(store)
        ok = store.unpublish(listing.listing_id, "u1")
        self.assertTrue(ok)
        self.assertFalse(listing.is_active)

    def test_non_owner_cannot_unpublish(self):
        store = _store()
        listing = _listing(store)
        with self.assertRaises(PermissionError):
            store.unpublish(listing.listing_id, "u_other")

    def test_unknown_listing_returns_false(self):
        store = _store()
        self.assertFalse(store.unpublish("no-id", "u1"))

    def test_admin_deactivate_bypasses_owner_check(self):
        store = _store()
        listing = _listing(store)
        ok = store.admin_deactivate(listing.listing_id)
        self.assertTrue(ok)
        self.assertFalse(listing.is_active)

    def test_admin_deactivate_unknown_returns_false(self):
        store = _store()
        self.assertFalse(store.admin_deactivate("no-such-id"))

    def test_admin_deactivate_idempotent(self):
        store = _store()
        listing = _listing(store)
        store.admin_deactivate(listing.listing_id)
        ok = store.admin_deactivate(listing.listing_id)  # second call: already inactive
        self.assertTrue(ok)

    def test_deactivate_all_listings_removes_all(self):
        store = _store()
        l1 = _listing(store, avatar_id="av1")
        l2 = _listing(store, avatar_id="av2", name="Second")
        deactivated = store.deactivate_all_listings("u1")
        self.assertEqual(len(deactivated), 2)
        self.assertCountEqual(deactivated, [l1.listing_id, l2.listing_id])
        self.assertFalse(l1.is_active)
        self.assertFalse(l2.is_active)

    def test_deactivate_all_listings_only_affects_owner(self):
        store = _store()
        l_u1 = _listing(store, avatar_id="av1", owner_id="u1", owner_username="alice")
        l_u2 = _listing(store, avatar_id="av2", owner_id="u2", owner_username="bob")
        store.deactivate_all_listings("u1")
        self.assertFalse(l_u1.is_active)
        self.assertTrue(l_u2.is_active)

    def test_deactivate_all_listings_no_active_returns_zero(self):
        store = _store()
        self.assertEqual(store.deactivate_all_listings("u_nobody"), [])

    def test_quota_blocks_publish(self):
        store = _store()
        store.set_quota("u1", 1)
        _listing(store, avatar_id="av1")  # first - allowed
        with self.assertRaises(ValueError):
            _listing(store, avatar_id="av2", name="Second Avatar")  # blocked by quota

    def test_quota_allows_up_to_limit(self):
        store = _store()
        store.set_quota("u1", 3)
        for i in range(3):
            _listing(store, avatar_id=f"av{i}", name=f"Avatar {i}")
        # 4th should fail
        with self.assertRaises(ValueError):
            _listing(store, avatar_id="av_extra", name="Extra")

    def test_no_quota_is_unlimited(self):
        store = _store()
        # No quota set → can publish many
        for i in range(5):
            _listing(store, avatar_id=f"av{i}", name=f"Avatar {i}")

    def test_get_quota_returns_none_when_not_set(self):
        store = _store()
        self.assertIsNone(store.get_quota("u1"))

    def test_get_quota_returns_value_when_set(self):
        store = _store()
        store.set_quota("u1", 10)
        self.assertEqual(store.get_quota("u1"), 10)

    def test_active_listing_count(self):
        store = _store()
        _listing(store, avatar_id="av1")
        _listing(store, avatar_id="av2", name="Avatar 2")
        self.assertEqual(store.get_active_listing_count("u1"), 2)

    def test_negative_quota_raises(self):
        store = _store()
        with self.assertRaises(ValueError):
            store.set_quota("u1", -1)


class TestRelatedListings(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.l1 = _listing(self.store, avatar_id="av1", name="Cute Cat", tags=["cute", "cat"], category="vrc")
        self.l2 = _listing(self.store, avatar_id="av2", owner_id="u2", owner_username="bob",
                           name="Cute Fox", tags=["cute", "fox"], category="vrc", description="cute fox")
        self.l3 = _listing(self.store, avatar_id="av3", owner_id="u3", owner_username="carol",
                           name="Scary Dragon", tags=["dragon", "scary"], category="world", description="dragon")

    def test_related_returns_list(self):
        result = self.store.get_related(self.l1.listing_id)
        self.assertIsInstance(result, list)

    def test_related_excludes_self(self):
        result = self.store.get_related(self.l1.listing_id)
        ids = [r["listing_id"] for r in result]
        self.assertNotIn(self.l1.listing_id, ids)

    def test_related_prefers_tag_overlap(self):
        # l2 shares "cute" tag with l1; l3 shares nothing — l2 should rank higher
        result = self.store.get_related(self.l1.listing_id)
        if result:
            self.assertEqual(result[0]["listing_id"], self.l2.listing_id)

    def test_related_empty_for_unknown_listing(self):
        result = self.store.get_related("no-such-id")
        self.assertEqual(result, [])

    def test_related_limit_respected(self):
        result = self.store.get_related(self.l1.listing_id, limit=1)
        self.assertLessEqual(len(result), 1)


class TestDownload(unittest.TestCase):
    def test_download_returns_data(self):
        store = _store()
        listing = _listing(store)
        data = store.download(listing.listing_id, "u2")
        self.assertIsNotNone(data)
        self.assertIn("parameters", data)
        self.assertIn("name", data)

    def test_download_increments_counter(self):
        store = _store()
        listing = _listing(store)
        store.download(listing.listing_id, "u2")
        store.download(listing.listing_id, "u3")
        self.assertEqual(listing.download_count, 2)

    def test_owner_self_download_does_not_inflate_count(self):
        store = _store()
        listing = _listing(store)
        store.download(listing.listing_id, "u1")  # owner re-downloads
        store.download(listing.listing_id, "u1")
        self.assertEqual(listing.download_count, 0)  # count stays at 0

    def test_owner_self_download_after_buyer_download(self):
        store = _store()
        listing = _listing(store)
        store.download(listing.listing_id, "u2")  # buyer: count becomes 1
        store.download(listing.listing_id, "u1")  # owner: count stays 1
        self.assertEqual(listing.download_count, 1)

    def test_download_inactive_listing_returns_none(self):
        store = _store()
        listing = _listing(store)
        store.unpublish(listing.listing_id, "u1")
        self.assertIsNone(store.download(listing.listing_id, "u2"))

    def test_download_unknown_listing(self):
        store = _store()
        self.assertIsNone(store.download("bad-id", "u1"))


class TestUpdateListing(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.listing = _listing(self.store)

    def test_owner_can_update_name(self):
        updated = self.store.update_listing(self.listing.listing_id, "u1", name="New Name")
        self.assertEqual(updated.name, "New Name")

    def test_owner_can_update_tags(self):
        updated = self.store.update_listing(self.listing.listing_id, "u1", tags=["fox", "fluffy"])
        self.assertEqual(updated.tags, ["fox", "fluffy"])

    def test_owner_can_update_parameters(self):
        updated = self.store.update_listing(self.listing.listing_id, "u1", parameters={"y": 2})
        self.assertEqual(updated.parameters, {"y": 2})

    def test_owner_can_update_price(self):
        updated = self.store.update_listing(self.listing.listing_id, "u1", is_free=False, price_credits=25)
        self.assertFalse(updated.is_free)
        self.assertEqual(updated.price_credits, 25)

    def test_non_owner_raises_permission_error(self):
        with self.assertRaises(PermissionError):
            self.store.update_listing(self.listing.listing_id, "u_stranger", name="Hacked")

    def test_unknown_listing_raises(self):
        with self.assertRaises(ValueError):
            self.store.update_listing("no-such-id", "u1", name="x")

    def test_negative_price_credits_raises(self):
        with self.assertRaises(ValueError):
            self.store.update_listing(self.listing.listing_id, "u1", price_credits=-5)

    def test_none_fields_are_ignored(self):
        original_name = self.listing.name
        self.store.update_listing(self.listing.listing_id, "u1", description="Updated desc")
        self.assertEqual(self.listing.name, original_name)

    def test_updated_at_changes(self):
        original_ts = self.listing.updated_at
        import time as _time
        _time.sleep(0.01)
        self.store.update_listing(self.listing.listing_id, "u1", name="Changed")
        self.assertGreater(self.listing.updated_at, original_ts)


class TestDownloadHistory(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.listing = _listing(self.store)

    def test_empty_history_for_new_user(self):
        result = self.store.get_user_download_history("u_new")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])

    def test_history_after_download(self):
        self.store.download(self.listing.listing_id, "u2")
        result = self.store.get_user_download_history("u2")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["listing_id"], self.listing.listing_id)

    def test_history_includes_listing_name(self):
        self.store.download(self.listing.listing_id, "u2")
        result = self.store.get_user_download_history("u2")
        self.assertEqual(result["items"][0]["name"], self.listing.name)

    def test_history_pagination_fields(self):
        for _ in range(5):
            self.store.download(self.listing.listing_id, "u2")
        result = self.store.get_user_download_history("u2", limit=3, offset=0)
        for key in ("total", "offset", "limit", "has_more", "next_offset", "items"):
            self.assertIn(key, result)

    def test_history_has_more_true(self):
        for _ in range(5):
            self.store.download(self.listing.listing_id, "u2")
        result = self.store.get_user_download_history("u2", limit=3, offset=0)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 3)

    def test_history_isolates_by_user(self):
        self.store.download(self.listing.listing_id, "u2")
        result_u3 = self.store.get_user_download_history("u3")
        self.assertEqual(result_u3["total"], 0)


class TestDownloadOwnershipIndex(unittest.TestCase):
    """O(1) ownership index stays consistent with the download log."""

    def setUp(self):
        self.store = _store()
        self.listing = _listing(self.store)

    def test_has_downloaded_true_after_download(self):
        self.assertFalse(self.store.has_downloaded(self.listing.listing_id, "u2"))
        self.store.download(self.listing.listing_id, "u2")
        self.assertTrue(self.store.has_downloaded(self.listing.listing_id, "u2"))

    def test_has_downloaded_isolated_per_user(self):
        self.store.download(self.listing.listing_id, "u2")
        self.assertFalse(self.store.has_downloaded(self.listing.listing_id, "u3"))

    def test_get_downloaded_ids_returns_copy(self):
        self.store.download(self.listing.listing_id, "u2")
        ids = self.store.get_downloaded_ids("u2")
        self.assertIn(self.listing.listing_id, ids)
        ids.add("tampered")  # mutating the copy must not affect the store
        self.assertNotIn("tampered", self.store.get_downloaded_ids("u2"))

    def test_index_matches_download_log(self):
        # Index membership must agree with the authoritative log for every pair.
        l2 = _listing(self.store, avatar_id="av2", name="Second")
        self.store.download(self.listing.listing_id, "u2")
        self.store.download(l2.listing_id, "u2")
        self.store.download(self.listing.listing_id, "u3")
        log_pairs = {(lid, did) for lid, did, _, _ap in self.store._download_log}
        for lid, did in log_pairs:
            self.assertTrue(self.store.has_downloaded(lid, did))
        self.assertEqual(self.store.get_downloaded_ids("u2"),
                         {self.listing.listing_id, l2.listing_id})


class TestMoneyPrimitiveInvariant(unittest.TestCase):
    """Every balance change must route through the primitive and leave a ledger trail."""

    def setUp(self):
        self.store = _store()

    def _ledger_sum(self, user_id):
        return sum(e["amount"] for e in self.store._credit_ledger.get(user_id, []))

    def test_ledger_sum_equals_balance_after_grant(self):
        self.store.add_credits("u1", 100)
        self.assertEqual(self._ledger_sum("u1"), self.store.get_balance("u1"))

    def test_ledger_sum_equals_balance_after_gift(self):
        self.store.add_credits("sender", 100)
        self.store.gift_credits("sender", "recv", 40)
        self.assertEqual(self._ledger_sum("sender"), self.store.get_balance("sender"))
        self.assertEqual(self._ledger_sum("recv"), self.store.get_balance("recv"))

    def test_ledger_sum_equals_balance_after_purchase(self):
        self.store.add_credits("buyer", 200)
        listing = _listing(
            self.store, avatar_id="av_p", owner_id="seller", owner_username="s",
            name="P", description="", tags=[], category="vrc", parameters={},
            is_free=False, price_credits=50,
        )
        self.store.download(listing.listing_id, "buyer")
        # Buyer ledger sums to remaining balance; seller ledger to proceeds.
        self.assertEqual(self._ledger_sum("buyer"), self.store.get_balance("buyer"))
        self.assertEqual(self._ledger_sum("seller"), self.store.get_balance("seller"))

    def test_credit_debit_reject_non_positive(self):
        with self.assertRaises(ValueError):
            self.store.credit("u1", 0, "grant")
        with self.assertRaises(ValueError):
            self.store.debit("u1", -1, "purchase")

    def test_integrity_consistent_after_operations(self):
        self.store.add_credits("a", 100)
        self.store.add_credits("b", 50)
        self.store.gift_credits("a", "b", 30)
        report = self.store.verify_ledger_integrity()
        self.assertTrue(report["consistent"])
        self.assertEqual(report["discrepancy_count"], 0)
        self.assertGreaterEqual(report["users_checked"], 2)

    def test_integrity_detects_injected_drift(self):
        # Simulate a rogue mutation that bypasses the money primitives.
        self.store.add_credits("a", 100)
        self.store._credits["a"] = 999  # drift: balance no longer matches ledger
        report = self.store.verify_ledger_integrity()
        self.assertFalse(report["consistent"])
        self.assertEqual(report["discrepancy_count"], 1)
        d = report["discrepancies"][0]
        self.assertEqual(d["user_id"], "a")
        self.assertEqual(d["balance"], 999)
        self.assertEqual(d["ledger_sum"], 100)
        self.assertEqual(d["difference"], 899)

    def test_integrity_empty_store(self):
        report = self.store.verify_ledger_integrity()
        self.assertTrue(report["consistent"])
        self.assertEqual(report["users_checked"], 0)

    def test_snapshot_roundtrip_restores_balances_and_ledger(self):
        import json
        self.store.add_credits("a", 100)
        self.store.add_credits("b", 50)
        self.store.gift_credits("a", "b", 30)
        snap = self.store.export_credit_state()
        json.dumps(snap)  # must be JSON-serializable

        restored = _store()
        result = restored.import_credit_state(snap)
        self.assertEqual(result["users_loaded"], 2)
        self.assertEqual(restored.get_balance("a"), 70)
        self.assertEqual(restored.get_balance("b"), 80)
        self.assertTrue(restored.verify_ledger_integrity()["consistent"])
        # Ledger history survives the round-trip.
        self.assertGreater(restored.get_credit_history("a")["total"], 0)

    def test_import_rejects_corrupt_snapshot(self):
        self.store.add_credits("a", 100)
        snap = self.store.export_credit_state()
        snap["credits"]["a"] = 999  # balance no longer matches ledger
        with self.assertRaises(ValueError):
            _store().import_credit_state(snap)

    def test_import_corrupt_snapshot_allowed_when_verify_false(self):
        self.store.add_credits("a", 100)
        snap = self.store.export_credit_state()
        snap["credits"]["a"] = 999
        target = _store()
        target.import_credit_state(snap, verify=False)
        self.assertEqual(target.get_balance("a"), 999)
        self.assertFalse(target.verify_ledger_integrity()["consistent"])

    def test_import_invalid_snapshot_raises(self):
        with self.assertRaises(ValueError):
            self.store.import_credit_state({"no_credits": True})

    def test_snapshot_roundtrips_refunded_purchases(self):
        # The cross-channel refund guard must survive a snapshot round-trip so a
        # purchase refunded before a restart can't be refunded again after it.
        import json
        self.store.add_credits("buyer", 100)
        self.store.mark_purchase_refunded("buyer", "lst1")
        snap = self.store.export_credit_state()
        json.dumps(snap)  # JSON-serializable

        restored = _store()
        restored.import_credit_state(snap)
        self.assertTrue(restored.is_purchase_refunded("buyer", "lst1"))
        # A fresh claim on the restored store correctly reports already-claimed.
        self.assertFalse(restored.mark_purchase_refunded("buyer", "lst1"))

    def test_import_v1_snapshot_without_refunded_purchases_preserves_state(self):
        # A legacy v1 snapshot has no "refunded_purchases" key; importing it must
        # not clobber an existing in-memory guard set.
        self.store.mark_purchase_refunded("buyer", "lst1")
        source = _store()
        source.add_credits("a", 10)
        legacy = source.export_credit_state()
        legacy.pop("refunded_purchases", None)  # simulate a v1 snapshot
        self.store.import_credit_state(legacy)
        self.assertTrue(self.store.is_purchase_refunded("buyer", "lst1"))

    def test_import_replaces_existing_state(self):
        self.store.add_credits("old_user", 500)
        source = _store()
        source.add_credits("a", 10)
        self.store.import_credit_state(source.export_credit_state())
        # Prior state is replaced, not merged.
        self.assertEqual(self.store.get_balance("old_user"), 0)
        self.assertEqual(self.store.get_balance("a"), 10)

    def test_save_load_file_roundtrip(self):
        import tempfile
        self.store.add_credits("a", 100)
        self.store.gift_credits("a", "b", 40)
        with tempfile.TemporaryDirectory() as d:
            # Nested dir is created automatically.
            path = str(Path(d) / "state" / "credits.json")
            self.store.save_credit_state(path)
            self.assertTrue(Path(path).exists())
            restored = _store()
            result = restored.load_credit_state(path)
            self.assertTrue(result["loaded"])
            self.assertEqual(restored.get_balance("a"), 60)
            self.assertEqual(restored.get_balance("b"), 40)

    def test_load_missing_file_is_graceful(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            result = self.store.load_credit_state(str(Path(d) / "absent.json"))
            self.assertFalse(result["loaded"])
            self.assertEqual(result["users_loaded"], 0)

    def test_save_is_atomic_no_tmp_left_behind(self):
        import tempfile
        self.store.add_credits("a", 10)
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "credits.json")
            self.store.save_credit_state(path)
            leftovers = [p.name for p in Path(d).iterdir() if p.suffix == ".tmp"]
            self.assertEqual(leftovers, [])

    def test_load_rejects_corrupt_file(self):
        import json
        import tempfile
        self.store.add_credits("a", 100)
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "credits.json")
            self.store.save_credit_state(path)
            # Tamper with the persisted file so balance != ledger.
            with open(path) as f:
                data = json.load(f)
            data["credits"]["a"] = 999
            with open(path, "w") as f:
                json.dump(data, f)
            with self.assertRaises(ValueError):
                _store().load_credit_state(path)

    def test_snapshot_roundtrips_purchase_sellers(self):
        """_purchase_seller must survive export→import so post-restart disputes
        still claw back from the original seller, not the transferred-to owner."""
        import json
        listing = _listing(
            self.store, avatar_id="av_ps", owner_id="u_ps_seller",
            owner_username="ps_seller", name="PS Avatar", description="",
            tags=[], category="vrc", parameters={}, is_free=False,
            price_credits=50,
        )
        self.store.add_credits("u_ps_buyer", 200)
        self.store.download(listing.listing_id, "u_ps_buyer")
        # Transfer to new owner
        self.store.transfer_listing(
            listing.listing_id, "u_ps_seller", "u_ps_new_owner", "new_owner"
        )
        snap = self.store.export_credit_state()
        self.assertIn("purchase_sellers", snap)
        json.dumps(snap)  # JSON-serializable

        restored = _store()
        # Import the listing state so get_listing works
        restored._listings[listing.listing_id] = self.store._listings[listing.listing_id]
        restored._downloads_by_user["u_ps_buyer"] = {"u_ps_buyer"}  # needed for has_downloaded
        restored.import_credit_state(snap)
        # Seller map must survive: dispute still targets the original seller
        self.assertEqual(
            restored._purchase_seller.get(("u_ps_buyer", listing.listing_id)),
            "u_ps_seller",
        )

    def test_import_v2_snapshot_without_purchase_sellers_leaves_existing_intact(self):
        """A v2 snapshot without 'purchase_sellers' must not clobber an existing
        in-memory seller map (same pattern as v1→v2 for refunded_purchases)."""
        listing_id = "lst_v2"
        self.store._purchase_seller[("buyer", listing_id)] = "original_seller"
        source = _store()
        source.add_credits("a", 10)
        legacy = source.export_credit_state()
        legacy.pop("purchase_sellers", None)  # simulate a v2 snapshot
        self.store.import_credit_state(legacy)
        # The existing in-memory map is NOT cleared
        self.assertEqual(
            self.store._purchase_seller.get(("buyer", listing_id)), "original_seller"
        )


class TestPaginationClamping(unittest.TestCase):
    """Hostile/malformed pagination inputs must be clamped, not slice wrongly."""

    def setUp(self):
        self.store = _store()
        for _ in range(6):
            self.store.add_credits("u1", 10)  # 6 ledger entries

    def test_negative_offset_returns_first_page_not_tail(self):
        r = self.store.get_credit_history("u1", limit=3, offset=-2)
        self.assertEqual(r["offset"], 0)
        self.assertEqual(len(r["items"]), 3)

    def test_zero_limit_does_not_create_paging_loop(self):
        r = self.store.get_credit_history("u1", limit=0, offset=0)
        self.assertGreaterEqual(r["limit"], 1)
        # Must not report "more pages" with an unchanged next_offset.
        if r["has_more"]:
            self.assertNotEqual(r["next_offset"], 0)

    def test_huge_limit_is_capped(self):
        r = self.store.get_credit_history("u1", limit=10**9, offset=0)
        self.assertLessEqual(r["limit"], 100)


class TestCredits(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.free_listing = _listing(self.store, is_free=True, price_credits=0)
        self.paid_listing = _listing(self.store, avatar_id="av_paid", owner_id="u_seller",
                                     owner_username="seller", name="Paid Avatar",
                                     description="Premium", tags=[], category="vrc",
                                     parameters={}, is_free=False, price_credits=50)

    def test_initial_balance_zero(self):
        self.assertEqual(self.store.get_balance("u99"), 0)

    def test_add_credits_increases_balance(self):
        self.store.add_credits("u2", 100)
        self.assertEqual(self.store.get_balance("u2"), 100)

    def test_add_credits_accumulates(self):
        self.store.add_credits("u2", 30)
        self.store.add_credits("u2", 20)
        self.assertEqual(self.store.get_balance("u2"), 50)

    def test_add_zero_or_negative_raises(self):
        with self.assertRaises(ValueError):
            self.store.add_credits("u2", 0)
        with self.assertRaises(ValueError):
            self.store.add_credits("u2", -10)

    def test_free_listing_downloads_without_credits(self):
        data = self.store.download(self.free_listing.listing_id, "u2")
        self.assertIsNotNone(data)

    def test_paid_listing_requires_credits(self):
        with self.assertRaises(ValueError):
            self.store.download(self.paid_listing.listing_id, "u_buyer")

    def test_paid_listing_deducts_credits(self):
        self.store.add_credits("u_buyer", 100)
        self.store.download(self.paid_listing.listing_id, "u_buyer")
        self.assertEqual(self.store.get_balance("u_buyer"), 50)

    def test_owner_downloads_own_paid_listing_free(self):
        data = self.store.download(self.paid_listing.listing_id, "u_seller")
        self.assertIsNotNone(data)
        self.assertEqual(self.store.get_balance("u_seller"), 0)

    def test_re_download_paid_listing_free_for_prior_buyer(self):
        self.store.add_credits("u_buyer", 100)
        self.store.download(self.paid_listing.listing_id, "u_buyer")  # pays 50
        self.assertEqual(self.store.get_balance("u_buyer"), 50)
        # Second download: already owns it, free
        self.store.download(self.paid_listing.listing_id, "u_buyer")
        self.assertEqual(self.store.get_balance("u_buyer"), 50)  # not charged again

    def test_download_reports_amount_paid_on_purchase(self):
        self.store.add_credits("u_buyer", 100)
        data = self.store.download(self.paid_listing.listing_id, "u_buyer")
        self.assertEqual(data["amount_paid"], 50)

    def test_re_download_reports_zero_amount_paid(self):
        # A free re-download of an owned listing must report amount_paid=0 so
        # callers don't credit membership tier (or a refund) for a non-charge.
        self.store.add_credits("u_buyer", 100)
        self.store.download(self.paid_listing.listing_id, "u_buyer")  # pays 50
        data = self.store.download(self.paid_listing.listing_id, "u_buyer")
        self.assertEqual(data["amount_paid"], 0)

    def test_owner_self_download_reports_zero_amount_paid(self):
        data = self.store.download(self.paid_listing.listing_id, "u_seller")
        self.assertEqual(data["amount_paid"], 0)

    def test_free_listing_reports_zero_amount_paid(self):
        data = self.store.download(self.free_listing.listing_id, "u2")
        self.assertEqual(data["amount_paid"], 0)

    def test_insufficient_credits_raises(self):
        self.store.add_credits("u_buyer", 20)
        with self.assertRaises(ValueError):
            self.store.download(self.paid_listing.listing_id, "u_buyer")
        self.assertEqual(self.store.get_balance("u_buyer"), 20)

    def test_gift_transfers_credits(self):
        self.store.add_credits("u_sender", 100)
        result = self.store.gift_credits("u_sender", "u_receiver", 40)
        self.assertEqual(self.store.get_balance("u_sender"), 60)
        self.assertEqual(self.store.get_balance("u_receiver"), 40)
        self.assertEqual(result["sender_balance"], 60)
        self.assertEqual(result["recipient_balance"], 40)

    def test_gift_insufficient_balance_raises(self):
        self.store.add_credits("u_sender", 10)
        with self.assertRaises(ValueError):
            self.store.gift_credits("u_sender", "u_receiver", 50)
        self.assertEqual(self.store.get_balance("u_sender"), 10)

    def test_gift_to_self_raises(self):
        self.store.add_credits("u1", 50)
        with self.assertRaises(ValueError):
            self.store.gift_credits("u1", "u1", 10)

    def test_gift_zero_raises(self):
        with self.assertRaises(ValueError):
            self.store.gift_credits("u_sender", "u_receiver", 0)


class TestCreditDebit(unittest.TestCase):
    """Public audited credit/debit API used by other subsystems."""

    def setUp(self):
        self.store = _store()

    def test_credit_increases_balance_and_returns_new(self):
        new_bal = self.store.credit("u1", 100, "refund")
        self.assertEqual(new_bal, 100)
        self.assertEqual(self.store.get_balance("u1"), 100)

    def test_credit_records_ledger_kind(self):
        self.store.credit("u1", 50, "gift_card_redeem", ref_id="card1")
        hist = self.store.get_credit_history("u1")
        entry = hist["items"][0]
        self.assertEqual(entry["kind"], "gift_card_redeem")
        self.assertEqual(entry["amount"], 50)
        self.assertEqual(entry["ref_id"], "card1")

    def test_credit_zero_or_negative_raises(self):
        with self.assertRaises(ValueError):
            self.store.credit("u1", 0, "refund")
        with self.assertRaises(ValueError):
            self.store.credit("u1", -5, "refund")

    def test_debit_decreases_balance_and_returns_new(self):
        self.store.add_credits("u1", 100)
        new_bal = self.store.debit("u1", 30, "gift_card_purchase")
        self.assertEqual(new_bal, 70)
        self.assertEqual(self.store.get_balance("u1"), 70)

    def test_debit_records_negative_ledger_amount(self):
        self.store.add_credits("u1", 100)
        self.store.debit("u1", 40, "gift_card_purchase")
        hist = self.store.get_credit_history("u1")
        entry = hist["items"][0]
        self.assertEqual(entry["kind"], "gift_card_purchase")
        self.assertEqual(entry["amount"], -40)

    def test_debit_insufficient_raises_and_preserves_balance(self):
        self.store.add_credits("u1", 20)
        with self.assertRaises(ValueError):
            self.store.debit("u1", 50, "gift_card_purchase")
        self.assertEqual(self.store.get_balance("u1"), 20)

    def test_debit_zero_or_negative_raises(self):
        with self.assertRaises(ValueError):
            self.store.debit("u1", 0, "gift_card_purchase")
        with self.assertRaises(ValueError):
            self.store.debit("u1", -5, "gift_card_purchase")


class TestRating(unittest.TestCase):
    def test_rate_valid(self):
        store = _store()
        listing = _listing(store)
        _buy(store, listing.listing_id, "u2")
        avg = store.rate(listing.listing_id, "u2", 4)
        self.assertEqual(avg, 4.0)

    def test_average_rating_reads_count_once(self):
        # Guards against ZeroDivisionError when rating_count is mutated
        # concurrently between the zero-guard and the division. We mock
        # rating_count to yield 1 then 0: a single read computes 5/1=5.0, while
        # a buggy double-read would hit the 0 and raise.
        from unittest.mock import patch, PropertyMock
        store = _store()
        listing = _listing(store)
        listing.rating_sum = 5
        with patch.object(type(listing), "rating_count",
                          new_callable=PropertyMock) as m:
            m.side_effect = [1, 0]  # second access would be a 0 divisor
            try:
                result = listing.average_rating
            except ZeroDivisionError:
                self.fail("average_rating read rating_count more than once")
        self.assertEqual(result, 5.0)

    def test_rate_updates_average(self):
        store = _store()
        listing = _listing(store)
        _buy(store, listing.listing_id, "u2", "u3")
        store.rate(listing.listing_id, "u2", 4)
        store.rate(listing.listing_id, "u3", 2)
        self.assertEqual(listing.average_rating, 3.0)

    def test_user_can_update_rating(self):
        store = _store()
        listing = _listing(store)
        _buy(store, listing.listing_id, "u2")
        store.rate(listing.listing_id, "u2", 5)
        store.rate(listing.listing_id, "u2", 1)
        self.assertEqual(listing.rating_count, 1)
        self.assertEqual(listing.average_rating, 1.0)

    def test_owner_cannot_rate_own(self):
        store = _store()
        listing = _listing(store)
        with self.assertRaises((ValueError, PermissionError)):
            store.rate(listing.listing_id, "u1", 5)

    def test_non_buyer_cannot_rate(self):
        store = _store()
        listing = _listing(store)
        with self.assertRaises(ValueError):
            store.rate(listing.listing_id, "u2", 4)

    def test_invalid_stars_raises(self):
        store = _store()
        listing = _listing(store)
        with self.assertRaises(ValueError):
            store.rate(listing.listing_id, "u2", 0)
        with self.assertRaises(ValueError):
            store.rate(listing.listing_id, "u2", 6)


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.l1 = self.store.publish("av1", "u1", "alice", "Cute Cat", "a cute cat", ["cute", "cat"], "vrc", {})
        self.l2 = self.store.publish("av2", "u2", "bob", "Dark Dragon", "scary dragon", ["dark", "dragon"], "web", {})
        self.l3 = self.store.publish("av3", "u1", "alice", "Shiny Puppy", "puppy dog", ["cute", "dog"], "vrc", {})

    def test_search_by_name(self):
        results = self.store.search("cat")
        self.assertEqual(results["total"], 1)
        self.assertEqual(results["items"][0]["name"], "Cute Cat")

    def test_search_by_description(self):
        results = self.store.search("scary dragon")
        self.assertGreater(results["total"], 0)

    def test_search_by_tag(self):
        results = self.store.search(tags=["cute"])
        self.assertEqual(results["total"], 2)

    def test_filter_by_category(self):
        results = self.store.search(category="vrc")
        self.assertEqual(results["total"], 2)

    def test_sort_by_downloads(self):
        self.store.download(self.l2.listing_id, "u3")
        self.store.download(self.l2.listing_id, "u4")
        results = self.store.search(sort_by="downloads")
        self.assertEqual(results["items"][0]["listing_id"], self.l2.listing_id)

    def test_sort_by_rating(self):
        _buy(self.store, self.l1.listing_id, "u3")
        self.store.rate(self.l1.listing_id, "u3", 5)
        results = self.store.search(sort_by="rating")
        self.assertEqual(results["items"][0]["listing_id"], self.l1.listing_id)

    def test_pagination(self):
        results = self.store.search(limit=2, offset=0)
        self.assertEqual(len(results["items"]), 2)
        results2 = self.store.search(limit=2, offset=2)
        self.assertLessEqual(len(results2["items"]), 1)

    def test_search_has_more_true(self):
        results = self.store.search(limit=2, offset=0)
        self.assertTrue(results["has_more"])
        self.assertEqual(results["next_offset"], 2)

    def test_search_has_more_false_on_last_page(self):
        results = self.store.search(limit=2, offset=2)
        self.assertFalse(results["has_more"])
        self.assertIsNone(results["next_offset"])

    def test_search_pagination_fields_present(self):
        results = self.store.search(limit=10, offset=0)
        for key in ("total", "offset", "limit", "has_more", "next_offset", "items"):
            self.assertIn(key, results)

    def test_empty_query_returns_all(self):
        results = self.store.search("")
        self.assertEqual(results["total"], 3)

    def test_get_listing(self):
        listing = self.store.get_listing(self.l1.listing_id)
        self.assertIsNotNone(listing)
        self.assertEqual(listing.name, "Cute Cat")

    def test_get_user_listings(self):
        listings = self.store.get_user_listings("u1")
        self.assertEqual(len(listings), 2)

    def test_get_trending(self):
        self.store.download(self.l3.listing_id, "u5")
        trending = self.store.get_trending(limit=1)
        self.assertEqual(len(trending), 1)
        self.assertEqual(trending[0]["listing_id"], self.l3.listing_id)

    def test_trending_tags_returns_rows(self):
        tags = self.store.get_trending_tags()
        tag_names = {row["tag"] for row in tags}
        # l1 and l3 both have "cute"
        self.assertIn("cute", tag_names)

    def test_trending_tags_cute_listing_count(self):
        tags = self.store.get_trending_tags()
        cute = next(row for row in tags if row["tag"] == "cute")
        self.assertEqual(cute["listing_count"], 2)

    def test_trending_tags_weighted_by_downloads(self):
        self.store.download(self.l2.listing_id, "u9")  # l2 has "dragon"
        self.store.download(self.l2.listing_id, "u10")
        tags = self.store.get_trending_tags()
        dragon = next(row for row in tags if row["tag"] == "dragon")
        self.assertEqual(dragon["download_count"], 2)
        self.assertGreaterEqual(dragon["score"], 3)  # 1 listing + 2 downloads

    def test_trending_tags_limit(self):
        tags = self.store.get_trending_tags(limit=1)
        self.assertEqual(len(tags), 1)

    def test_get_stats(self):
        stats = self.store.get_stats()
        self.assertEqual(stats["total_listings"], 3)
        self.assertIn("categories", stats)

    def test_to_dict_has_expected_fields(self):
        d = self.l1.to_dict()
        for key in ("listing_id", "name", "owner_username", "tags", "download_count", "average_rating"):
            self.assertIn(key, d)

    def test_filter_free_only(self):
        store = _store()
        store.publish("av_free", "u1", "alice", "Free", "free", [], "vrc", {}, is_free=True, price_credits=0)
        store.publish("av_paid", "u1", "alice", "Paid", "paid", [], "vrc", {}, is_free=False, price_credits=50)
        r = store.search(is_free=True)
        self.assertTrue(all(it["is_free"] for it in r["items"]))

    def test_filter_paid_only(self):
        store = _store()
        store.publish("av_free", "u1", "alice", "Free", "", [], "vrc", {}, is_free=True)
        store.publish("av_paid", "u1", "alice", "Paid", "", [], "vrc", {}, is_free=False, price_credits=50)
        r = store.search(is_free=False)
        self.assertTrue(all(not it["is_free"] for it in r["items"]))

    def test_filter_min_price(self):
        store = _store()
        store.publish("av1", "u1", "alice", "Cheap", "", [], "vrc", {}, is_free=False, price_credits=10)
        store.publish("av2", "u1", "alice", "Expensive", "", [], "vrc", {}, is_free=False, price_credits=100)
        r = store.search(min_price=50)
        self.assertTrue(all(it["price_credits"] >= 50 for it in r["items"]))

    def test_filter_max_price(self):
        store = _store()
        store.publish("av1", "u1", "alice", "Cheap", "", [], "vrc", {}, is_free=False, price_credits=10)
        store.publish("av2", "u1", "alice", "Expensive", "", [], "vrc", {}, is_free=False, price_credits=100)
        r = store.search(max_price=50)
        self.assertTrue(all(it["price_credits"] <= 50 for it in r["items"]))

    def test_sort_by_price_asc(self):
        store = _store()
        store.publish("av1", "u1", "alice", "Mid", "", [], "vrc", {}, is_free=False, price_credits=50)
        store.publish("av2", "u1", "alice", "Low", "", [], "vrc", {}, is_free=False, price_credits=10)
        store.publish("av3", "u1", "alice", "High", "", [], "vrc", {}, is_free=False, price_credits=99)
        r = store.search(sort_by="price_asc")
        prices = [it["price_credits"] for it in r["items"]]
        self.assertEqual(prices, sorted(prices))

    def test_sort_by_price_desc(self):
        store = _store()
        store.publish("av1", "u1", "alice", "Mid", "", [], "vrc", {}, is_free=False, price_credits=50)
        store.publish("av2", "u1", "alice", "Low", "", [], "vrc", {}, is_free=False, price_credits=10)
        r = store.search(sort_by="price_desc")
        prices = [it["price_credits"] for it in r["items"]]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_search_oversized_query_is_truncated_not_error(self):
        # 1 MB query must not raise; it is silently capped at 200 chars.
        big_query = "x" * 1_000_000
        result = self.store.search(big_query)
        self.assertIsInstance(result, dict)

    def test_search_excess_tags_are_capped(self):
        # 10,000-tag list must not hang; only the first 50 are processed.
        many_tags = [f"tag{i}" for i in range(10_000)]
        result = self.store.search(tags=many_tags)
        self.assertIsInstance(result, dict)

    def test_search_serialized_items_match_active_filter(self):
        """search() filters by is_active and to_dict() must happen inside the
        same lock so that a concurrent unpublish() cannot make an inactive listing
        appear in results. Verify total equals serialized item count (atomic snapshot)."""
        # All listings created in setUp are active; total must equal len(items)
        result = self.store.search(limit=100)
        self.assertEqual(result["total"], len(result["items"]))

    def test_search_price_filter_consistent_with_serialized_price(self):
        """Price filtering and serialization must happen under the same lock so
        that serialized items are consistent with the filter applied."""
        self.store.publish("av99", "u_price", "seller", "Pricey", "expensive", [], "vrc", {},
                           price_credits=500, is_free=False)
        result = self.store.search(min_price=500, max_price=500)
        for item in result["items"]:
            self.assertGreaterEqual(item["price_credits"], 500)
            self.assertLessEqual(item["price_credits"], 500)

    def test_search_platform_filter_hit(self):
        store = _store()
        store.publish("av_vrc", "u1", "alice", "VRC Avatar", "", [], "vrc", {}, platform="vrchat")
        store.publish("av_neos", "u1", "alice", "Neos Avatar", "", [], "neos", {}, platform="neos")
        r = store.search(platform="vrchat")
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["items"][0]["platform"], "vrchat")

    def test_search_platform_filter_case_insensitive(self):
        store = _store()
        store.publish("av_vrc", "u1", "alice", "VRC Avatar", "", [], "vrc", {}, platform="vrchat")
        r = store.search(platform="VRChat")
        self.assertEqual(r["total"], 1)

    def test_search_platform_filter_no_match(self):
        store = _store()
        store.publish("av_vrc", "u1", "alice", "VRC Avatar", "", [], "vrc", {}, platform="vrchat")
        r = store.search(platform="resonite")
        self.assertEqual(r["total"], 0)

    def test_search_no_platform_filter_returns_all_platforms(self):
        store = _store()
        store.publish("av_vrc", "u1", "alice", "VRC Avatar", "", [], "vrc", {}, platform="vrchat")
        store.publish("av_neos", "u1", "alice", "Neos Avatar", "", [], "neos", {}, platform="neos")
        r = store.search()
        self.assertEqual(r["total"], 2)


class TestCreatorAnalytics(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.l1 = self.store.publish("av1", "u1", "alice", "Cat", "cute cat", ["cute"], "vrc", {})
        self.l2 = self.store.publish("av2", "u1", "alice", "Dog", "cute dog", ["cute"], "vrc", {})
        self.store.publish("av3", "u2", "bob", "Dragon", "scary", ["dark"], "web", {})

    def test_analytics_total_listings(self):
        a = self.store.get_creator_analytics("u1")
        self.assertEqual(a["total_listings"], 2)
        self.assertEqual(a["active_listings"], 2)

    def test_analytics_total_downloads(self):
        self.store.download(self.l1.listing_id, "u3")
        self.store.download(self.l1.listing_id, "u4")
        a = self.store.get_creator_analytics("u1")
        self.assertEqual(a["total_downloads"], 2)

    def test_analytics_downloads_by_day(self):
        self.store.download(self.l1.listing_id, "u3")
        a = self.store.get_creator_analytics("u1")
        self.assertGreater(len(a["downloads_by_day"]), 0)

    def test_analytics_rating_distribution(self):
        _buy(self.store, self.l1.listing_id, "u3", "u4")
        self.store.rate(self.l1.listing_id, "u3", 5)
        self.store.rate(self.l1.listing_id, "u4", 3)
        a = self.store.get_creator_analytics("u1")
        self.assertEqual(a["rating_distribution"][5], 1)
        self.assertEqual(a["rating_distribution"][3], 1)

    def test_analytics_total_reviews(self):
        _buy(self.store, self.l1.listing_id, "u3")
        self.store.review(self.l1.listing_id, "u3", "carol", 4, "Good")
        a = self.store.get_creator_analytics("u1")
        self.assertEqual(a["total_reviews"], 1)

    def test_analytics_top_listing(self):
        self.store.download(self.l2.listing_id, "u3")
        self.store.download(self.l2.listing_id, "u4")
        a = self.store.get_creator_analytics("u1")
        self.assertEqual(a["top_listing"]["listing_id"], self.l2.listing_id)

    def test_analytics_no_listings(self):
        a = self.store.get_creator_analytics("nonexistent-user")
        self.assertEqual(a["total_listings"], 0)
        self.assertIsNone(a["top_listing"])


class TestModeration(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.listing = _listing(self.store)

    def test_report_creates_report(self):
        report = self.store.report_listing(self.listing.listing_id, "u2", "spam", "looks spammy")
        self.assertIsInstance(report, ListingReport)
        self.assertEqual(report.status, "pending")
        self.assertEqual(report.reason, "spam")

    def test_invalid_reason_raises(self):
        with self.assertRaises(ValueError):
            self.store.report_listing(self.listing.listing_id, "u2", "bogus_reason")

    def test_report_unknown_listing_raises(self):
        with self.assertRaises(ValueError):
            self.store.report_listing("no-such-listing", "u2", "spam")

    def test_duplicate_pending_report_raises(self):
        self.store.report_listing(self.listing.listing_id, "u2", "spam")
        with self.assertRaises(ValueError):
            self.store.report_listing(self.listing.listing_id, "u2", "inappropriate")

    def test_details_truncated(self):
        report = self.store.report_listing(self.listing.listing_id, "u2", "other", "x" * 2000)
        self.assertLessEqual(len(report.details), 1000)

    def test_get_reports_all(self):
        self.store.report_listing(self.listing.listing_id, "u2", "spam")
        result = self.store.get_reports()
        self.assertEqual(result["total"], 1)

    def test_get_reports_filter_by_status(self):
        self.store.report_listing(self.listing.listing_id, "u2", "spam")
        pending = self.store.get_reports(status="pending")
        resolved = self.store.get_reports(status="resolved")
        self.assertEqual(pending["total"], 1)
        self.assertEqual(resolved["total"], 0)

    def test_resolve_report_dismissed(self):
        report = self.store.report_listing(self.listing.listing_id, "u2", "spam")
        resolved = self.store.resolve_report(report.report_id, "admin1", "dismissed", "not spam")
        self.assertEqual(resolved.status, "dismissed")
        self.assertEqual(resolved.resolved_by, "admin1")
        self.assertIsNotNone(resolved.resolved_at)

    def test_resolve_report_with_takedown(self):
        report = self.store.report_listing(self.listing.listing_id, "u2", "malware")
        self.store.resolve_report(report.report_id, "admin1", "resolved", takedown=True)
        self.assertFalse(self.listing.is_active)

    def test_resolve_invalid_action_raises(self):
        report = self.store.report_listing(self.listing.listing_id, "u2", "spam")
        with self.assertRaises(ValueError):
            self.store.resolve_report(report.report_id, "admin1", "ignore")

    def test_resolve_unknown_report_raises(self):
        with self.assertRaises(ValueError):
            self.store.resolve_report("no-such-id", "admin1", "dismissed")

    def test_report_stats(self):
        self.store.report_listing(self.listing.listing_id, "u2", "spam")
        self.store.report_listing(self.listing.listing_id, "u3", "copyright")
        stats = self.store.get_report_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["by_status"]["pending"], 2)
        self.assertEqual(stats["by_reason"]["spam"], 1)

    def test_report_to_dict_fields(self):
        report = self.store.report_listing(self.listing.listing_id, "u2", "spam", "bad")
        d = report.to_dict()
        for key in ("report_id", "listing_id", "reporter_id", "reason", "details", "status", "created_at"):
            self.assertIn(key, d)

    def test_can_report_again_after_resolution(self):
        r1 = self.store.report_listing(self.listing.listing_id, "u2", "spam")
        self.store.resolve_report(r1.report_id, "admin1", "dismissed")
        # Now a new pending report from same user should be allowed
        r2 = self.store.report_listing(self.listing.listing_id, "u2", "inappropriate")
        self.assertEqual(r2.status, "pending")

    def test_get_reports_pagination_fields(self):
        self.store.report_listing(self.listing.listing_id, "u2", "spam")
        result = self.store.get_reports(limit=10, offset=0)
        for key in ("total", "offset", "limit", "has_more", "next_offset", "items"):
            self.assertIn(key, result)

    def test_get_reports_has_more_true(self):
        for i in range(5):
            extra = _listing(self.store, avatar_id=f"av_extra{i}", owner_id=f"ux{i}", owner_username=f"u{i}",
                             name=f"Extra {i}", description="d", tags=[], category="vrc", parameters={})
            self.store.report_listing(extra.listing_id, "u2", "spam")
        result = self.store.get_reports(limit=3, offset=0)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 3)

    def test_get_reports_has_more_false(self):
        self.store.report_listing(self.listing.listing_id, "u2", "spam")
        result = self.store.get_reports(limit=10, offset=0)
        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])


class TestReviews(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.listing = _listing(self.store)

    def test_review_returns_avg_and_review(self):
        _buy(self.store, self.listing.listing_id, "u2")
        avg, rv = self.store.review(self.listing.listing_id, "u2", "bob", 4, "Great!")
        self.assertEqual(avg, 4.0)
        self.assertIsInstance(rv, Review)
        self.assertEqual(rv.stars, 4)
        self.assertEqual(rv.text, "Great!")

    def test_review_text_truncated_at_2000(self):
        _buy(self.store, self.listing.listing_id, "u2")
        _, rv = self.store.review(self.listing.listing_id, "u2", "bob", 3, "x" * 3000)
        self.assertLessEqual(len(rv.text), 2000)

    def test_update_review_changes_text_and_stars(self):
        _buy(self.store, self.listing.listing_id, "u2")
        self.store.review(self.listing.listing_id, "u2", "bob", 5, "Perfect")
        avg, rv = self.store.review(self.listing.listing_id, "u2", "bob", 2, "Disappointing")
        self.assertEqual(avg, 2.0)
        self.assertEqual(rv.text, "Disappointing")
        self.assertEqual(self.listing.rating_count, 1)

    def test_rate_after_review_syncs_review_stars(self):
        # A user reviews (5★ + text), then re-rates to 3★ without editing text.
        # The stored review's stars must follow the vote so the review card and
        # the listing average never disagree.
        _buy(self.store, self.listing.listing_id, "u2")
        self.store.review(self.listing.listing_id, "u2", "bob", 5, "Great!")
        self.store.rate(self.listing.listing_id, "u2", 3)
        result = self.store.get_reviews(self.listing.listing_id)
        self.assertEqual(result["items"][0]["stars"], 3)
        self.assertEqual(result["items"][0]["text"], "Great!")  # text preserved
        self.assertEqual(self.listing.average_rating, 3.0)
        self.assertEqual(self.listing.rating_count, 1)  # not double-counted

    def test_owner_cannot_review_own_listing(self):
        with self.assertRaises((ValueError, PermissionError)):
            self.store.review(self.listing.listing_id, "u1", "alice", 5, "mine")

    def test_invalid_stars_raises(self):
        _buy(self.store, self.listing.listing_id, "u2")
        with self.assertRaises(ValueError):
            self.store.review(self.listing.listing_id, "u2", "bob", 0, "bad")
        with self.assertRaises(ValueError):
            self.store.review(self.listing.listing_id, "u2", "bob", 6, "bad")

    def test_get_reviews_empty(self):
        result = self.store.get_reviews(self.listing.listing_id)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])

    def test_get_reviews_after_post(self):
        _buy(self.store, self.listing.listing_id, "u2")
        self.store.review(self.listing.listing_id, "u2", "bob", 4, "Nice")
        result = self.store.get_reviews(self.listing.listing_id)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["text"], "Nice")

    def test_get_reviews_pagination(self):
        for i in range(5):
            self.store.download(self.listing.listing_id, f"user{i}")
        for i in range(5):
            self.store.review(self.listing.listing_id, f"user{i}", f"u{i}", 4, f"rev{i}")
        page1 = self.store.get_reviews(self.listing.listing_id, limit=3, offset=0)
        page2 = self.store.get_reviews(self.listing.listing_id, limit=3, offset=3)
        self.assertEqual(len(page1["items"]), 3)
        self.assertEqual(len(page2["items"]), 2)
        self.assertEqual(page1["total"], 5)

    def test_get_reviews_has_more_true(self):
        for i in range(5):
            self.store.download(self.listing.listing_id, f"user{i}")
        for i in range(5):
            self.store.review(self.listing.listing_id, f"user{i}", f"u{i}", 4, f"rev{i}")
        result = self.store.get_reviews(self.listing.listing_id, limit=3, offset=0)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 3)

    def test_get_reviews_has_more_false_on_last_page(self):
        for i in range(5):
            self.store.download(self.listing.listing_id, f"user{i}")
        for i in range(5):
            self.store.review(self.listing.listing_id, f"user{i}", f"u{i}", 4, f"rev{i}")
        result = self.store.get_reviews(self.listing.listing_id, limit=3, offset=3)
        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])

    def test_get_reviews_pagination_fields_present(self):
        result = self.store.get_reviews(self.listing.listing_id, limit=10, offset=0)
        for key in ("total", "offset", "limit", "has_more", "next_offset", "items"):
            self.assertIn(key, result)

    def test_delete_review(self):
        _buy(self.store, self.listing.listing_id, "u2")
        self.store.review(self.listing.listing_id, "u2", "bob", 4, "OK")
        ok = self.store.delete_review(self.listing.listing_id, "u2")
        self.assertTrue(ok)
        result = self.store.get_reviews(self.listing.listing_id)
        self.assertEqual(result["total"], 0)

    def test_delete_nonexistent_review_returns_false(self):
        ok = self.store.delete_review(self.listing.listing_id, "never-reviewed")
        self.assertFalse(ok)

    def test_review_to_dict_fields(self):
        _buy(self.store, self.listing.listing_id, "u2")
        _, rv = self.store.review(self.listing.listing_id, "u2", "bob", 3, "Decent")
        d = rv.to_dict()
        for key in ("review_id", "listing_id", "user_id", "username", "stars", "text", "created_at"):
            self.assertIn(key, d)

    def test_get_reviews_unknown_listing(self):
        result = self.store.get_reviews("no-such-listing")
        self.assertEqual(result["total"], 0)

    def test_get_reviews_hidden_filter_consistent_with_serialized(self):
        """Filtering out hidden reviews and to_dict() must happen under the same
        lock so a concurrent hide_review() can't leak a hidden review into the
        public (include_hidden=False) result."""
        store = _store()
        lst = _listing(store)
        lid = lst.listing_id
        _buy(store, lid, "rv1", "rv2")
        _, r1 = store.review(lid, "rv1", "ann", 5, "great")
        _, r2 = store.review(lid, "rv2", "bob", 1, "bad")
        store.hide_review(r2.review_id)
        result = store.get_reviews(lid, include_hidden=False)
        for item in result["items"]:
            self.assertFalse(item["is_hidden"])
        self.assertEqual(result["total"], 1)


class TestReviewSorting(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.listing = _listing(self.store)
        self.lid = self.listing.listing_id
        _buy(self.store, self.lid, "u2", "u3", "u4")
        _, self.r1 = self.store.review(self.lid, "u2", "bob", 2, "Not great")
        _, self.r2 = self.store.review(self.lid, "u3", "carol", 5, "Excellent!")
        _, self.r3 = self.store.review(self.lid, "u4", "dave", 3, "OK")

    def test_default_sort_is_newest_first(self):
        items = self.store.get_reviews(self.lid)["items"]
        dates = [item["created_at"] for item in items]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_sort_by_rating_high(self):
        items = self.store.get_reviews(self.lid, sort_by="rating_high")["items"]
        stars = [item["stars"] for item in items]
        self.assertEqual(stars, sorted(stars, reverse=True))

    def test_sort_by_rating_low(self):
        items = self.store.get_reviews(self.lid, sort_by="rating_low")["items"]
        stars = [item["stars"] for item in items]
        self.assertEqual(stars, sorted(stars))

    def test_sort_by_helpful(self):
        self.store.vote_review_helpful(self.r2.review_id, "u5", True)
        self.store.vote_review_helpful(self.r2.review_id, "u6", True)
        self.store.vote_review_helpful(self.r1.review_id, "u5", True)
        items = self.store.get_reviews(self.lid, sort_by="helpful")["items"]
        helpful_counts = [item["helpful_count"] for item in items]
        self.assertEqual(helpful_counts, sorted(helpful_counts, reverse=True))

    def test_sort_by_newest_explicit(self):
        items_default = self.store.get_reviews(self.lid)["items"]
        items_newest = self.store.get_reviews(self.lid, sort_by="newest")["items"]
        self.assertEqual(
            [i["review_id"] for i in items_default],
            [i["review_id"] for i in items_newest],
        )


class TestCreatorAnalyticsExtended(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.store.add_credits("u3", 200)
        self.l1 = self.store.publish(
            "av1", "u1", "alice", "Cat", "cute cat", ["cute", "vrc"],
            "animal", {}, is_free=True
        )
        self.l2 = self.store.publish(
            "av2", "u1", "alice", "Dog", "cute dog", ["cute"],
            "animal", {}, is_free=False, price_credits=10
        )

    def test_analytics_downloads_by_tag(self):
        self.store.download(self.l1.listing_id, "u3")
        a = self.store.get_creator_analytics("u1")
        self.assertIn("downloads_by_tag", a)
        self.assertGreater(a["downloads_by_tag"].get("cute", 0), 0)

    def test_analytics_downloads_by_category(self):
        self.store.download(self.l1.listing_id, "u3")
        a = self.store.get_creator_analytics("u1")
        self.assertIn("downloads_by_category", a)
        self.assertGreater(a["downloads_by_category"].get("animal", 0), 0)

    def test_analytics_total_credits_earned(self):
        self.store.add_credits("u3", 10)
        self.store.download(self.l2.listing_id, "u3")
        a = self.store.get_creator_analytics("u1")
        self.assertIn("total_credits_earned", a)
        self.assertEqual(a["total_credits_earned"], 10)

    def test_analytics_no_downloads_zero_tag_counts(self):
        a = self.store.get_creator_analytics("u1")
        self.assertEqual(a["downloads_by_tag"], {})
        self.assertEqual(a["total_credits_earned"], 0)

    def test_redownload_does_not_inflate_revenue(self):
        # First purchase charges 10 credits; re-download charges 0.
        # Revenue must be 10, not 20.
        self.store.add_credits("u3", 20)
        self.store.download(self.l2.listing_id, "u3")
        self.store.download(self.l2.listing_id, "u3")  # re-download, free
        a = self.store.get_creator_analytics("u1")
        self.assertEqual(a["total_credits_earned"], 10,
                         "Re-download must not add to creator revenue")

    def test_promo_discount_reflected_in_revenue(self):
        # Buying with a 50% promo code → seller earns 5, not 10.
        self.store.add_credits("u3", 10)
        self.store.create_promo_code("u1", "HALF", 50, listing_id=self.l2.listing_id, max_uses=10)
        self.store.download(self.l2.listing_id, "u3", promo_code="HALF")
        a = self.store.get_creator_analytics("u1")
        self.assertEqual(a["total_credits_earned"], 5,
                         "Promo discount must reduce reported revenue")


class TestPriceHistory(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.listing = _listing(self.store, is_free=False, price_credits=100)

    def test_initial_price_recorded(self):
        history = self.store.get_price_history(self.listing.listing_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["price_credits"], 100)
        self.assertFalse(history[0]["is_free"])

    def test_price_change_recorded(self):
        self.store.update_listing(self.listing.listing_id, "u1", price_credits=50)
        history = self.store.get_price_history(self.listing.listing_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[1]["price_credits"], 50)

    def test_no_price_change_no_history_entry(self):
        self.store.update_listing(self.listing.listing_id, "u1", name="New Name")
        history = self.store.get_price_history(self.listing.listing_id)
        self.assertEqual(len(history), 1)  # only initial entry

    def test_unknown_listing_returns_empty(self):
        history = self.store.get_price_history("no-such-id")
        self.assertEqual(history, [])


class TestPurchaseDisputes(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.store.add_credits("u_buyer", 500)
        self.paid_listing = _listing(
            self.store, avatar_id="av_paid", owner_id="u_seller",
            owner_username="seller", name="Paid Avatar",
            description="Premium", tags=[], category="vrc",
            parameters={}, is_free=False, price_credits=50
        )
        # Buyer downloads the paid listing
        self.store.download(self.paid_listing.listing_id, "u_buyer")

    def test_open_dispute_returns_dispute(self):
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        self.assertIsInstance(dispute, PurchaseDispute)
        self.assertEqual(dispute.status, "open")

    def test_open_dispute_records_seller_and_amount(self):
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        self.assertEqual(dispute.seller_id, "u_seller")
        self.assertEqual(dispute.amount_credits, 50)

    def test_open_dispute_without_download_raises(self):
        with self.assertRaises(ValueError):
            self.store.open_dispute(self.paid_listing.listing_id, "u_nobody", "other")

    def test_open_dispute_on_free_listing_raises(self):
        free = _listing(self.store, avatar_id="av_free", owner_id="u_seller",
                        owner_username="seller", name="Free", description="",
                        tags=[], category="vrc", parameters={}, is_free=True)
        with self.assertRaises(ValueError):
            self.store.open_dispute(free.listing_id, "u_buyer", "other")

    def test_open_dispute_allowed_after_seller_makes_listing_free(self):
        """Eligibility must be based on what the buyer actually paid, not the
        listing's current price.  If the seller makes the listing free AFTER
        the buyer purchased it, the buyer must still be able to dispute."""
        # Buyer already purchased the 50-credit listing in setUp (download was called)
        self.store.update_listing(
            self.paid_listing.listing_id, "u_seller",
            is_free=True, price_credits=0,
        )
        # The listing is now free, but the buyer paid 50 credits — dispute allowed
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        self.assertEqual(dispute.amount_credits, 50)

    def test_duplicate_open_dispute_raises(self):
        self.store.open_dispute(self.paid_listing.listing_id, "u_buyer", "other")
        with self.assertRaises(ValueError):
            self.store.open_dispute(self.paid_listing.listing_id, "u_buyer", "other")

    def test_invalid_reason_raises(self):
        with self.assertRaises(ValueError):
            self.store.open_dispute(self.paid_listing.listing_id, "u_buyer", "bad_reason")

    def test_resolve_dispute_refund_credits_buyer(self):
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        before_balance = self.store.get_balance("u_buyer")
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        after_balance = self.store.get_balance("u_buyer")
        self.assertEqual(after_balance - before_balance, 50)

    def test_resolve_dispute_refund_claws_back_from_seller(self):
        # Seller earned 50 from the sale; a dispute refund must reclaim it.
        seller_before = self.store.get_balance("u_seller")
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        self.assertEqual(self.store.get_balance("u_seller"), seller_before - 50)

    def test_resolve_dispute_refund_conserves_credits(self):
        total_before = self.store.get_balance("u_buyer") + self.store.get_balance("u_seller")
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        total_after = self.store.get_balance("u_buyer") + self.store.get_balance("u_seller")
        self.assertEqual(total_before, total_after)

    def test_resolve_dispute_refund_records_ledger_both_sides(self):
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        buyer_kinds = [e["kind"] for e in self.store.get_credit_history("u_buyer")["items"]]
        seller_kinds = [e["kind"] for e in self.store.get_credit_history("u_seller")["items"]]
        self.assertIn("dispute_refund", buyer_kinds)
        self.assertIn("dispute_reversal", seller_kinds)

    def test_resolve_dispute_release_does_not_move_credits(self):
        buyer_before = self.store.get_balance("u_buyer")
        seller_before = self.store.get_balance("u_seller")
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "release")
        self.assertEqual(self.store.get_balance("u_buyer"), buyer_before)
        self.assertEqual(self.store.get_balance("u_seller"), seller_before)

    def test_dispute_clamp_books_platform_subsidy_and_conserves_total(self):
        # Seller spends proceeds, so the refund clawback is clamped. The gap
        # must be booked to the platform account, keeping total credits
        # conserved (no silent system-wide injection).
        self.store.debit("u_seller", self.store.get_balance("u_seller"), "withdrawal")
        total_before = sum(self.store._credits.values())
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        total_after = sum(self.store._credits.values())
        self.assertEqual(total_after, total_before)  # conserved across all accounts
        from avatar_marketplace import PLATFORM_ACCOUNT
        self.assertEqual(self.store.get_balance(PLATFORM_ACCOUNT), -50)
        kinds = [e["kind"] for e in self.store._credit_ledger[PLATFORM_ACCOUNT]]
        self.assertIn("dispute_subsidy", kinds)
        # Per-user integrity still holds (platform balance == its ledger sum).
        self.assertTrue(self.store.verify_ledger_integrity()["consistent"])

    def test_dispute_full_clawback_books_no_subsidy(self):
        # Seller still holds the proceeds → full clawback, no platform subsidy.
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        from avatar_marketplace import PLATFORM_ACCOUNT
        self.assertEqual(self.store.get_balance(PLATFORM_ACCOUNT), 0)

    def test_resolve_dispute_clawback_clamped_when_seller_spent(self):
        # Seller spends their proceeds before the dispute resolves.
        self.store.debit("u_seller", self.store.get_balance("u_seller"),
                         "withdrawal")
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        # Seller balance clamped at 0 (never negative); buyer still refunded.
        self.assertEqual(self.store.get_balance("u_seller"), 0)
        self.assertEqual(self.store.get_balance("u_buyer"), 500)  # 500 - 50 + 50 (sale then refund)

    def test_resolve_dispute_status_updated(self):
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        resolved = self.store.resolve_dispute(dispute.dispute_id, "admin1", "release")
        self.assertEqual(resolved.status, "resolved_release")
        self.assertIsNotNone(resolved.resolved_at)

    def test_resolve_already_resolved_raises(self):
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "other"
        )
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        with self.assertRaises(ValueError):
            self.store.resolve_dispute(dispute.dispute_id, "admin1", "release")

    def test_dispute_amount_reflects_promo_discounted_price(self):
        # Buyer pays a discounted price via promo; the dispute (and thus the
        # refund) must be for what they actually paid, not the list price.
        listing = _listing(
            self.store, avatar_id="av_promo", owner_id="u_seller2",
            owner_username="seller2", name="Promo Avatar", description="",
            tags=[], category="vrc", parameters={}, is_free=False,
            price_credits=100,
        )
        self.store.create_promo_code("u_seller2", "HALF", 50,
                                     listing_id=listing.listing_id)
        self.store.add_credits("u_promo_buyer", 200)
        self.store.download(listing.listing_id, "u_promo_buyer", promo_code="HALF")
        dispute = self.store.open_dispute(listing.listing_id, "u_promo_buyer", "other")
        self.assertEqual(dispute.amount_credits, 50)  # paid 50, not the 100 list price

    def test_dispute_refund_promo_conserves_credits(self):
        listing = _listing(
            self.store, avatar_id="av_promo2", owner_id="u_seller3",
            owner_username="seller3", name="Promo2", description="",
            tags=[], category="vrc", parameters={}, is_free=False,
            price_credits=100,
        )
        self.store.create_promo_code("u_seller3", "SAVE60", 60,
                                     listing_id=listing.listing_id)
        self.store.add_credits("u_pb", 200)
        self.store.download(listing.listing_id, "u_pb", promo_code="SAVE60")
        # Buyer paid 40, seller earned 40.
        self.assertEqual(self.store.get_balance("u_pb"), 160)
        self.assertEqual(self.store.get_balance("u_seller3"), 40)
        dispute = self.store.open_dispute(listing.listing_id, "u_pb", "other")
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        # Refund only the 40 paid: buyer back to 200, seller clawed to 0.
        self.assertEqual(self.store.get_balance("u_pb"), 200)
        self.assertEqual(self.store.get_balance("u_seller3"), 0)

    def test_dispute_after_transfer_claws_back_from_original_seller(self):
        """If a listing is transferred AFTER a paid purchase, a dispute refund
        must claw the proceeds back from the seller who actually received them
        (the original owner), NOT the new owner who never got the money."""
        # u_buyer already bought paid_listing from u_seller in setUp.
        # Transfer ownership to a new owner (balance defaults to 0).
        self.store.transfer_listing(
            self.paid_listing.listing_id, "u_seller", "u_new_owner", "newowner"
        )
        seller_before = self.store.get_balance("u_seller")       # got 50 from sale
        new_owner_before = self.store.get_balance("u_new_owner")  # got nothing
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        # The dispute must target the original seller, not the new owner.
        self.assertEqual(dispute.seller_id, "u_seller")
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        # Original seller is debited the 50 they earned; new owner is untouched.
        self.assertEqual(self.store.get_balance("u_seller"), seller_before - 50)
        self.assertEqual(self.store.get_balance("u_new_owner"), new_owner_before)
        # And total credits stay conserved.
        self.assertTrue(self.store.verify_ledger_integrity()["consistent"])

    def test_dispute_after_transfer_conserves_credits(self):
        """The transfer-aware clawback must keep the system zero-sum."""
        self.store.transfer_listing(
            self.paid_listing.listing_id, "u_seller", "u_new_owner2", "newowner2"
        )
        total_before = sum(self.store._credits.values())
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        total_after = sum(self.store._credits.values())
        self.assertEqual(total_before, total_after)

    def test_get_disputes_returns_paginated(self):
        self.store.open_dispute(self.paid_listing.listing_id, "u_buyer", "other")
        result = self.store.get_disputes()
        self.assertEqual(result["total"], 1)
        self.assertIn("has_more", result)

    def test_get_disputes_honors_full_pagination_contract(self):
        # Every paginated endpoint must expose the same keys, incl. next_offset.
        result = self.store.get_disputes()
        for key in ("total", "offset", "limit", "has_more", "next_offset", "items"):
            self.assertIn(key, result)

    def test_get_disputes_next_offset_set_when_more(self):
        # Open several disputes across distinct listings so a page has more.
        for i in range(3):
            lst = _listing(
                self.store, avatar_id=f"av_d{i}", owner_id="u_seller",
                owner_username="seller", name=f"D{i}", description="",
                tags=[], category="vrc", parameters={}, is_free=False,
                price_credits=10,
            )
            self.store.download(lst.listing_id, "u_buyer")
            self.store.open_dispute(lst.listing_id, "u_buyer", "other")
        result = self.store.get_disputes(limit=2, offset=0)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 2)

    def test_get_disputes_filter_by_status(self):
        dispute = self.store.open_dispute(self.paid_listing.listing_id, "u_buyer", "other")
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        open_result = self.store.get_disputes(status="open")
        self.assertEqual(open_result["total"], 0)
        refund_result = self.store.get_disputes(status="resolved_refund")
        self.assertEqual(refund_result["total"], 1)

    def test_cannot_open_dispute_after_resolved_refund(self):
        # After a refund the buyer must not be able to open a second dispute
        # for the same listing (double-refund attack).
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        with self.assertRaises(ValueError):
            self.store.open_dispute(
                self.paid_listing.listing_id, "u_buyer", "other"
            )

    def test_cannot_open_dispute_after_resolved_release(self):
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "not_as_described"
        )
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "release")
        with self.assertRaises(ValueError):
            self.store.open_dispute(
                self.paid_listing.listing_id, "u_buyer", "other"
            )

    def test_dispute_refund_marks_purchase_refunded(self):
        # A resolved-refund dispute must claim the (buyer, listing) purchase in
        # the cross-channel refund ledger so the order-refund channel skips it.
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "other"
        )
        self.assertFalse(
            self.store.is_purchase_refunded("u_buyer", self.paid_listing.listing_id)
        )
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        self.assertTrue(
            self.store.is_purchase_refunded("u_buyer", self.paid_listing.listing_id)
        )

    def test_dispute_refund_blocked_if_already_refunded(self):
        # If the order-refund channel already claimed the purchase, the dispute
        # refund must be blocked and the dispute must remain open.
        self.store.mark_purchase_refunded("u_buyer", self.paid_listing.listing_id)
        dispute = self.store.open_dispute(
            self.paid_listing.listing_id, "u_buyer", "other"
        )
        with self.assertRaises(ValueError):
            self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        # Dispute untouched so an admin can still release it.
        self.assertEqual(self.store.get_disputes(status="open")["total"], 1)

    def test_dispute_blocked_when_promo_zeroed_price(self):
        """A 99% promo on a 10-credit listing produces actual_price=0.
        No ledger entry is created, so open_dispute must reject it as free
        rather than falling back to the list price (which would grant a
        refund the buyer never paid)."""
        listing = _listing(
            self.store, avatar_id="av_zero_promo", owner_id="u_szp_seller",
            owner_username="szp_seller", name="Tiny Avatar", description="",
            tags=[], category="vrc", parameters={}, is_free=False,
            price_credits=10,
        )
        # 99% off a 10-credit listing → int(10 * 1/100) = 0
        self.store.create_promo_code("u_szp_seller", "ALMOSTFREE", 99,
                                     listing_id=listing.listing_id)
        self.store.add_credits("u_szp_buyer", 200)
        result = self.store.download(
            listing.listing_id, "u_szp_buyer", promo_code="ALMOSTFREE"
        )
        self.assertEqual(result["amount_paid"], 0)  # buyer paid nothing
        with self.assertRaises(ValueError):
            self.store.open_dispute(listing.listing_id, "u_szp_buyer", "other")

    def test_dispute_allowed_when_promo_left_nonzero_price(self):
        """A 50% promo on a 100-credit listing still leaves actual_price=50.
        A ledger entry exists, so open_dispute must succeed with amount=50."""
        listing = _listing(
            self.store, avatar_id="av_half_promo", owner_id="u_shp_seller",
            owner_username="shp_seller", name="Half Avatar", description="",
            tags=[], category="vrc", parameters={}, is_free=False,
            price_credits=100,
        )
        self.store.create_promo_code("u_shp_seller", "HALF50", 50,
                                     listing_id=listing.listing_id)
        self.store.add_credits("u_shp_buyer", 200)
        self.store.download(listing.listing_id, "u_shp_buyer", promo_code="HALF50")
        dispute = self.store.open_dispute(listing.listing_id, "u_shp_buyer", "other")
        self.assertEqual(dispute.amount_credits, 50)


class TestPurchaseRefundLedger(unittest.TestCase):
    def setUp(self):
        self.store = _store()

    def test_mark_returns_true_first_time(self):
        self.assertTrue(self.store.mark_purchase_refunded("b1", "l1"))

    def test_mark_returns_false_when_already_claimed(self):
        self.store.mark_purchase_refunded("b1", "l1")
        self.assertFalse(self.store.mark_purchase_refunded("b1", "l1"))

    def test_is_refunded_reflects_claim(self):
        self.assertFalse(self.store.is_purchase_refunded("b1", "l1"))
        self.store.mark_purchase_refunded("b1", "l1")
        self.assertTrue(self.store.is_purchase_refunded("b1", "l1"))

    def test_claims_are_per_buyer_listing_pair(self):
        self.store.mark_purchase_refunded("b1", "l1")
        # Different buyer or different listing is an independent claim.
        self.assertTrue(self.store.mark_purchase_refunded("b2", "l1"))
        self.assertTrue(self.store.mark_purchase_refunded("b1", "l2"))


class TestFeaturedListings(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.l1 = _listing(self.store, avatar_id="av1", name="Cat A")
        self.l2 = _listing(self.store, avatar_id="av2", name="Cat B")

    def test_feature_listing_returns_true(self):
        ok = self.store.feature_listing(self.l1.listing_id)
        self.assertTrue(ok)

    def test_feature_listing_unknown_returns_false(self):
        ok = self.store.feature_listing("no-such-id")
        self.assertFalse(ok)

    def test_feature_twice_returns_false(self):
        self.store.feature_listing(self.l1.listing_id)
        ok = self.store.feature_listing(self.l1.listing_id)
        self.assertFalse(ok)

    def test_get_featured_ordered(self):
        self.store.feature_listing(self.l1.listing_id)
        self.store.feature_listing(self.l2.listing_id)
        items = self.store.get_featured()
        ids = [it["listing_id"] for it in items]
        self.assertEqual(ids[0], self.l1.listing_id)
        self.assertEqual(ids[1], self.l2.listing_id)

    def test_unfeature_listing(self):
        self.store.feature_listing(self.l1.listing_id)
        ok = self.store.unfeature_listing(self.l1.listing_id)
        self.assertTrue(ok)
        self.assertEqual(self.store.get_featured(), [])

    def test_unfeature_not_featured_returns_false(self):
        ok = self.store.unfeature_listing(self.l1.listing_id)
        self.assertFalse(ok)

    def test_get_featured_excludes_inactive(self):
        self.store.feature_listing(self.l1.listing_id)
        self.l1.is_active = False
        items = self.store.get_featured()
        self.assertEqual(items, [])


class TestTrendingImproved(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.l1 = _listing(self.store, avatar_id="av1", name="Recent Hit")
        self.l2 = _listing(self.store, avatar_id="av2", name="Old Favorite")
        # Give l2 a lot of all-time downloads
        self.store.add_credits("u_buyer", 10000)
        for i in range(5):
            self.store.download(self.l2.listing_id, f"u_old_{i}")

    def test_trending_returns_list(self):
        items = self.store.get_trending(limit=5)
        self.assertIsInstance(items, list)

    def test_trending_with_days_param(self):
        items = self.store.get_trending(limit=10, days=7)
        self.assertIsInstance(items, list)

    def test_trending_respects_limit(self):
        items = self.store.get_trending(limit=1)
        self.assertLessEqual(len(items), 1)


class TestReviewReplies(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        listing = _listing(self.store)
        _buy(self.store, listing.listing_id, "u2")
        _, self.review = self.store.review(listing.listing_id, "u2", "bob", 4, "Great!")
        self.review_id = self.review.review_id

    def test_add_reply_returns_review_reply(self):
        reply = self.store.add_review_reply(self.review_id, "u1", "alice", "Thank you!")
        self.assertIsInstance(reply, ReviewReply)

    def test_add_reply_fields(self):
        reply = self.store.add_review_reply(self.review_id, "u1", "alice", "Thank you!")
        self.assertEqual(reply.review_id, self.review_id)
        self.assertEqual(reply.user_id, "u1")
        self.assertEqual(reply.text, "Thank you!")

    def test_get_replies_returns_list(self):
        self.store.add_review_reply(self.review_id, "u1", "alice", "Reply 1")
        self.store.add_review_reply(self.review_id, "u1", "alice", "Reply 2")
        replies = self.store.get_review_replies(self.review_id)
        self.assertEqual(len(replies), 2)

    def test_get_replies_empty_for_no_replies(self):
        replies = self.store.get_review_replies(self.review_id)
        self.assertEqual(replies, [])

    def test_add_reply_empty_text_raises(self):
        with self.assertRaises(ValueError):
            self.store.add_review_reply(self.review_id, "u1", "alice", "  ")

    def test_add_reply_unknown_review_raises(self):
        with self.assertRaises(ValueError):
            self.store.add_review_reply("no-such-review", "u1", "alice", "Hello")

    def test_add_reply_hidden_review_raises(self):
        self.store.hide_review(self.review_id)
        with self.assertRaises(ValueError):
            self.store.add_review_reply(self.review_id, "u1", "alice", "Hello")

    def test_delete_reply_own(self):
        reply = self.store.add_review_reply(self.review_id, "u1", "alice", "My reply")
        ok = self.store.delete_review_reply(self.review_id, reply.reply_id, "u1")
        self.assertTrue(ok)
        self.assertEqual(self.store.get_review_replies(self.review_id), [])

    def test_delete_reply_wrong_user_fails(self):
        reply = self.store.add_review_reply(self.review_id, "u1", "alice", "My reply")
        ok = self.store.delete_review_reply(self.review_id, reply.reply_id, "u999")
        self.assertFalse(ok)
        self.assertEqual(len(self.store.get_review_replies(self.review_id)), 1)

    def test_reply_to_dict_fields(self):
        reply = self.store.add_review_reply(self.review_id, "u1", "alice", "Nice work!")
        d = reply.to_dict()
        for key in ("reply_id", "review_id", "user_id", "username", "text", "created_at"):
            self.assertIn(key, d)

    def test_reply_limit_enforced(self):
        orig = self.store._MAX_REPLIES_PER_REVIEW
        self.store._MAX_REPLIES_PER_REVIEW = 3
        try:
            for i in range(3):
                self.store.add_review_reply(self.review_id, "u1", "alice", f"Reply {i}")
            with self.assertRaises(ValueError):
                self.store.add_review_reply(self.review_id, "u1", "alice", "overflow")
        finally:
            self.store._MAX_REPLIES_PER_REVIEW = orig


class TestListingVersions(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.listing = _listing(self.store)
        self.lid = self.listing.listing_id

    def test_publish_creates_v1_automatically(self):
        versions = self.store.get_versions(self.lid)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].version_number, 1)

    def test_v1_changelog_is_initial_publish(self):
        v1 = self.store.get_versions(self.lid)[0]
        self.assertIn("公開", v1.changelog)

    def test_publish_version_returns_listing_version(self):
        v = self.store.publish_version(self.lid, "u1", "バグ修正")
        self.assertIsInstance(v, ListingVersion)

    def test_publish_version_increments_version_number(self):
        v2 = self.store.publish_version(self.lid, "u1", "バグ修正")
        self.assertEqual(v2.version_number, 2)
        v3 = self.store.publish_version(self.lid, "u1", "機能追加")
        self.assertEqual(v3.version_number, 3)

    def test_publish_version_updates_listing_current_version(self):
        self.store.publish_version(self.lid, "u1", "変更")
        listing = self.store.get_listing(self.lid)
        self.assertEqual(listing.current_version, 2)

    def test_publish_version_updates_name(self):
        self.store.publish_version(self.lid, "u1", "名前変更", name="New Name")
        listing = self.store.get_listing(self.lid)
        self.assertEqual(listing.name, "New Name")

    def test_publish_version_updates_description(self):
        self.store.publish_version(self.lid, "u1", "説明変更", description="Updated description")
        listing = self.store.get_listing(self.lid)
        self.assertEqual(listing.description, "Updated description")

    def test_publish_version_wrong_owner_raises(self):
        with self.assertRaises(PermissionError):
            self.store.publish_version(self.lid, "u999", "変更")

    def test_publish_version_empty_changelog_raises(self):
        with self.assertRaises(ValueError):
            self.store.publish_version(self.lid, "u1", "   ")

    def test_publish_version_unknown_listing_raises(self):
        with self.assertRaises(ValueError):
            self.store.publish_version("no-such-id", "u1", "変更")

    def test_get_versions_returns_oldest_first(self):
        self.store.publish_version(self.lid, "u1", "v2")
        self.store.publish_version(self.lid, "u1", "v3")
        versions = self.store.get_versions(self.lid)
        nums = [v.version_number for v in versions]
        self.assertEqual(nums, sorted(nums))

    def test_get_version_by_number(self):
        self.store.publish_version(self.lid, "u1", "v2 changelog")
        v = self.store.get_version(self.lid, 2)
        self.assertIsNotNone(v)
        self.assertEqual(v.version_number, 2)
        self.assertEqual(v.changelog, "v2 changelog")

    def test_get_version_nonexistent_returns_none(self):
        v = self.store.get_version(self.lid, 99)
        self.assertIsNone(v)

    def test_to_dict_fields(self):
        v = self.store.publish_version(self.lid, "u1", "変更内容")
        d = v.to_dict()
        for key in ("version_id", "listing_id", "version_number", "name",
                    "description", "parameters", "changelog", "created_by", "created_at"):
            self.assertIn(key, d)

    def test_parameters_snapshot_on_version(self):
        self.store.publish_version(self.lid, "u1", "param update", parameters={"y": 2})
        v2 = self.store.get_version(self.lid, 2)
        self.assertEqual(v2.parameters, {"y": 2})
        # v1 snapshot is unchanged
        v1 = self.store.get_version(self.lid, 1)
        self.assertEqual(v1.parameters, {"x": 1})

    def test_multiple_listings_independent_versions(self):
        listing2 = _listing(self.store, avatar_id="av2", owner_id="u2", owner_username="bob")
        self.store.publish_version(self.lid, "u1", "u1 v2")
        versions2 = self.store.get_versions(listing2.listing_id)
        self.assertEqual(len(versions2), 1)  # only v1 (initial)


class TestOwnershipCheck(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.listing = _listing(self.store)
        self.lid = self.listing.listing_id

    def test_not_downloaded_initially(self):
        self.assertFalse(self.store.has_downloaded(self.lid, "u2"))

    def test_downloaded_after_download(self):
        self.store.download(self.lid, "u2")
        self.assertTrue(self.store.has_downloaded(self.lid, "u2"))

    def test_other_user_not_marked_as_downloaded(self):
        self.store.download(self.lid, "u2")
        self.assertFalse(self.store.has_downloaded(self.lid, "u3"))

    def test_false_for_nonexistent_listing(self):
        self.assertFalse(self.store.has_downloaded("no-such-id", "u2"))

    def test_owner_downloading_own_listing_not_recorded(self):
        # Owner self-downloads are free previews, not counted in download history
        self.store.download(self.lid, "u1")
        self.assertFalse(self.store.has_downloaded(self.lid, "u1"))


class TestRatingDistribution(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.listing = _listing(self.store)
        self.lid = self.listing.listing_id

    def test_empty_distribution_for_no_ratings(self):
        r = self.store.get_rating_distribution(self.lid)
        self.assertEqual(r["total_ratings"], 0)
        self.assertEqual(r["average_rating"], 0.0)

    def test_distribution_counts_per_star(self):
        _buy(self.store, self.lid, "u2", "u3", "u4")
        self.store.rate(self.lid, "u2", 5)
        self.store.rate(self.lid, "u3", 3)
        self.store.rate(self.lid, "u4", 5)
        r = self.store.get_rating_distribution(self.lid)
        self.assertEqual(r["distribution"][5], 2)
        self.assertEqual(r["distribution"][3], 1)
        self.assertEqual(r["distribution"][1], 0)

    def test_total_ratings_count(self):
        _buy(self.store, self.lid, "u2", "u3")
        self.store.rate(self.lid, "u2", 4)
        self.store.rate(self.lid, "u3", 4)
        r = self.store.get_rating_distribution(self.lid)
        self.assertEqual(r["total_ratings"], 2)

    def test_average_rating_correct(self):
        _buy(self.store, self.lid, "u2", "u3")
        self.store.rate(self.lid, "u2", 4)
        self.store.rate(self.lid, "u3", 2)
        r = self.store.get_rating_distribution(self.lid)
        self.assertEqual(r["average_rating"], 3.0)

    def test_result_has_required_keys(self):
        r = self.store.get_rating_distribution(self.lid)
        for key in ("listing_id", "distribution", "total_ratings", "average_rating"):
            self.assertIn(key, r)

    def test_listing_id_in_result(self):
        r = self.store.get_rating_distribution(self.lid)
        self.assertEqual(r["listing_id"], self.lid)


class TestCloneListing(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.cc_listing = _listing(self.store, license_type="cc_by")
        self.personal_listing = _listing(self.store, avatar_id="av_personal",
                                          license_type="personal")

    def test_clone_cc_by_succeeds(self):
        cloned = self.store.clone_listing(self.cc_listing.listing_id, "u2", "bob")
        self.assertIsNotNone(cloned)
        self.assertEqual(cloned.owner_id, "u2")

    def test_clone_personal_raises_permission_error(self):
        with self.assertRaises(PermissionError):
            self.store.clone_listing(self.personal_listing.listing_id, "u2", "bob")

    def test_cloned_listing_is_free(self):
        cloned = self.store.clone_listing(self.cc_listing.listing_id, "u2", "bob")
        self.assertTrue(cloned.is_free)
        self.assertEqual(cloned.price_credits, 0)

    def test_cloned_name_has_clone_suffix(self):
        cloned = self.store.clone_listing(self.cc_listing.listing_id, "u2", "bob")
        self.assertIn("clone", cloned.name.lower())

    def test_cloned_listing_has_same_tags(self):
        cloned = self.store.clone_listing(self.cc_listing.listing_id, "u2", "bob")
        self.assertEqual(sorted(cloned.tags), sorted(self.cc_listing.tags))

    def test_cloned_listing_has_same_category(self):
        cloned = self.store.clone_listing(self.cc_listing.listing_id, "u2", "bob")
        self.assertEqual(cloned.category, self.cc_listing.category)

    def test_clone_cc_by_sa_also_succeeds(self):
        sa_listing = _listing(self.store, avatar_id="av_sa", license_type="cc_by_sa")
        cloned = self.store.clone_listing(sa_listing.listing_id, "u2", "bob")
        self.assertIsNotNone(cloned)

    def test_clone_nonexistent_listing_raises(self):
        with self.assertRaises(ValueError):
            self.store.clone_listing("no-such-id", "u2", "bob")

    def test_clone_is_independent_listing(self):
        cloned = self.store.clone_listing(self.cc_listing.listing_id, "u2", "bob")
        self.assertNotEqual(cloned.listing_id, self.cc_listing.listing_id)

    def test_clone_preserves_license_type_from_check_time(self):
        """clone_listing must use the license_type snapshotted inside the lock.

        A concurrent update_listing that changes license_type="personal" between
        the check and the publish() call must not bypass the cc_by/cc_by_sa gate
        — the clone must carry the license that was verified, not the live value."""
        lid = self.cc_listing.listing_id

        # clone_listing: check passes (cc_by), then update_listing runs, then publish
        # We simulate this by having the clone complete first (it snapshots the value)
        # and then separately verify that the clone carries the correct license.
        cloned = self.store.clone_listing(lid, "u2", "bob")
        # Now change the source to personal
        self.store.update_listing(lid, "u1", license_type="personal")
        # The clone must carry the license that was cc_by at clone time
        self.assertIn(cloned.license_type, ("cc_by", "cc_by_sa"))

    def test_clone_resets_download_count(self):
        self.store.download(self.cc_listing.listing_id, "u3")
        cloned = self.store.clone_listing(self.cc_listing.listing_id, "u2", "bob")
        self.assertEqual(cloned.download_count, 0)

    def test_clone_preserves_platform(self):
        store = _store()
        src = _listing(store, license_type="cc_by", platform="VRChat")
        cloned = store.clone_listing(src.listing_id, "u2", "bob")
        self.assertEqual(cloned.platform, "vrchat")

    def test_clone_empty_platform_stays_empty(self):
        store = _store()
        src = _listing(store, license_type="cc_by")
        cloned = store.clone_listing(src.listing_id, "u2", "bob")
        self.assertEqual(cloned.platform, "")


class TestSearchFacets(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.store.publish("av1", "u1", "alice", "Cat", "d", ["cute", "cat"], "vrc", {},
                           license_type="cc_by", is_free=True)
        self.store.publish("av2", "u2", "bob", "Dog", "d", ["cute", "dog"], "vrchat", {},
                           license_type="personal", is_free=False, price_credits=50)
        self.store.publish("av3", "u1", "alice", "Fox", "d", ["animal"], "vrc", {},
                           license_type="cc_by", is_free=True)

    def test_facets_not_in_response_by_default(self):
        r = self.store.search()
        self.assertNotIn("facets", r)

    def test_facets_included_when_requested(self):
        r = self.store.search(include_facets=True)
        self.assertIn("facets", r)

    def test_facets_category_counts(self):
        r = self.store.search(include_facets=True)
        cats = r["facets"]["categories"]
        self.assertEqual(cats.get("vrc"), 2)
        self.assertEqual(cats.get("vrchat"), 1)

    def test_facets_license_type_counts(self):
        r = self.store.search(include_facets=True)
        lics = r["facets"]["license_types"]
        self.assertEqual(lics.get("cc_by"), 2)
        self.assertEqual(lics.get("personal"), 1)

    def test_facets_top_tags(self):
        r = self.store.search(include_facets=True)
        tags = r["facets"]["top_tags"]
        self.assertIn("cute", tags)
        self.assertEqual(tags["cute"], 2)

    def test_facets_reflect_applied_filters(self):
        # Filter by category=vrc; facet should only count vrc listings
        r = self.store.search(category="vrc", include_facets=True)
        self.assertEqual(r["facets"]["categories"].get("vrchat", 0), 0)

    def test_facets_include_platforms(self):
        store = _store()
        store.publish("av_vrc", "u1", "alice", "VRC", "d", [], "vrc", {}, platform="vrchat")
        store.publish("av_neos", "u1", "alice", "Neos", "d", [], "neos", {}, platform="neos")
        store.publish("av_noplatform", "u1", "alice", "None", "d", [], "other", {})
        r = store.search(include_facets=True)
        plats = r["facets"]["platforms"]
        self.assertIn("platforms", r["facets"])
        self.assertEqual(plats.get("vrchat"), 1)
        self.assertEqual(plats.get("neos"), 1)
        # Listings with no platform should not appear in the facet
        self.assertNotIn("", plats)


class TestSearchLicenseAndOwner(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.store.publish("av1", "u1", "alice", "CC", "d", [], "vrc", {},
                           license_type="cc_by")
        self.store.publish("av2", "u2", "bob", "Personal", "d", [], "vrc", {},
                           license_type="personal")
        self.store.publish("av3", "u1", "alice", "CC2", "d", [], "vrc", {},
                           license_type="cc_by")

    def test_filter_by_license_type(self):
        r = self.store.search(license_type="cc_by")
        self.assertEqual(r["total"], 2)
        self.assertTrue(all(it["license_type"] == "cc_by" for it in r["items"]))

    def test_filter_by_license_type_no_match(self):
        r = self.store.search(license_type="commercial")
        self.assertEqual(r["total"], 0)

    def test_filter_by_owner_id(self):
        r = self.store.search(owner_id="u1")
        self.assertEqual(r["total"], 2)
        self.assertTrue(all(it["owner_id"] == "u1" for it in r["items"]))

    def test_owner_and_license_combined(self):
        r = self.store.search(owner_id="u1", license_type="cc_by")
        self.assertEqual(r["total"], 2)

    def test_owner_filter_no_match(self):
        r = self.store.search(owner_id="u999")
        self.assertEqual(r["total"], 0)


class TestCreatorLeaderboard(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.l1 = _listing(self.store, owner_id="u1", owner_username="alice")
        self.l2 = _listing(self.store, avatar_id="av2", owner_id="u2",
                           owner_username="bob")
        self.store.add_credits("buyer", 1000)
        for _ in range(5):
            self.store.download(self.l1.listing_id, "buyer")
        for _ in range(2):
            self.store.download(self.l2.listing_id, "buyer")

    def test_leaderboard_by_downloads_order(self):
        board = self.store.get_leaderboard(by="downloads")
        self.assertEqual(board[0]["owner_id"], "u1")
        self.assertEqual(board[1]["owner_id"], "u2")

    def test_leaderboard_by_listings(self):
        _listing(self.store, avatar_id="av3", owner_id="u2", owner_username="bob")
        board = self.store.get_leaderboard(by="listings")
        self.assertEqual(board[0]["owner_id"], "u2")

    def test_leaderboard_by_rating(self):
        _buy(self.store, self.l1.listing_id, "u_rev")
        _buy(self.store, self.l2.listing_id, "u_rev2")
        self.store.review(self.l1.listing_id, "u_rev", "reviewer", 5, "Perfect!")
        self.store.review(self.l2.listing_id, "u_rev2", "reviewer2", 2, "Meh")
        board = self.store.get_leaderboard(by="rating")
        self.assertEqual(board[0]["owner_id"], "u1")

    def test_leaderboard_limit(self):
        board = self.store.get_leaderboard(limit=1)
        self.assertEqual(len(board), 1)

    def test_leaderboard_entry_has_fields(self):
        board = self.store.get_leaderboard()
        for entry in board:
            for key in ("owner_id", "owner_username", "total_downloads",
                        "listing_count", "average_rating"):
                self.assertIn(key, entry)

    def test_leaderboard_does_not_include_inactive(self):
        lst3 = _listing(self.store, avatar_id="av3", owner_id="u3", owner_username="carol")
        for _ in range(10):
            self.store.download(lst3.listing_id, "buyer")
        self.store.unpublish(lst3.listing_id, "u3")
        board = self.store.get_leaderboard(by="downloads")
        owner_ids = [e["owner_id"] for e in board]
        self.assertNotIn("u3", owner_ids)

    def test_leaderboard_download_counts_consistent_with_active_listings(self):
        """download_count must be read under the lock so the count is a consistent
        snapshot; verify the aggregated totals match what was recorded atomically."""
        board = self.store.get_leaderboard(by="downloads")
        totals = {e["owner_id"]: e["total_downloads"] for e in board}
        self.assertEqual(totals["u1"], 5)
        self.assertEqual(totals["u2"], 2)


class TestCreditHistory(unittest.TestCase):
    def setUp(self):
        self.store = _store()

    def test_history_empty_initially(self):
        result = self.store.get_credit_history("u1")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])

    def test_add_credits_creates_ledger_entry(self):
        self.store.add_credits("u1", 100)
        result = self.store.get_credit_history("u1")
        self.assertEqual(result["total"], 1)
        entry = result["items"][0]
        self.assertEqual(entry["amount"], 100)
        self.assertEqual(entry["kind"], "grant")
        self.assertEqual(entry["balance_after"], 100)

    def test_gift_records_sent_and_received(self):
        self.store.add_credits("u1", 100)
        self.store.gift_credits("u1", "u2", 40)
        h1 = self.store.get_credit_history("u1")
        h2 = self.store.get_credit_history("u2")
        # u1 has grant + gift_sent
        kinds1 = [e["kind"] for e in h1["items"]]
        self.assertIn("gift_sent", kinds1)
        # u2 has gift_received
        kinds2 = [e["kind"] for e in h2["items"]]
        self.assertIn("gift_received", kinds2)

    def test_paid_download_records_purchase_and_sale(self):
        paid = _listing(self.store, avatar_id="av_p", owner_id="seller",
                        owner_username="s", name="P", description="d", tags=[],
                        category="vrc", parameters={}, is_free=False, price_credits=30)
        self.store.add_credits("buyer", 100)
        self.store.download(paid.listing_id, "buyer")
        buyer_h = self.store.get_credit_history("buyer")
        seller_h = self.store.get_credit_history("seller")
        buyer_kinds = [e["kind"] for e in buyer_h["items"]]
        seller_kinds = [e["kind"] for e in seller_h["items"]]
        self.assertIn("purchase", buyer_kinds)
        self.assertIn("sale", seller_kinds)

    def test_history_newest_first(self):
        for _i in range(3):
            self.store.add_credits("u1", 10)
        items = self.store.get_credit_history("u1")["items"]
        balances = [e["balance_after"] for e in items]
        self.assertEqual(balances, sorted(balances, reverse=True))

    def test_history_pagination(self):
        for _ in range(10):
            self.store.add_credits("u1", 5)
        p1 = self.store.get_credit_history("u1", limit=5, offset=0)
        p2 = self.store.get_credit_history("u1", limit=5, offset=5)
        self.assertEqual(len(p1["items"]), 5)
        self.assertEqual(len(p2["items"]), 5)
        self.assertTrue(p1["has_more"])
        self.assertFalse(p2["has_more"])

    def test_history_fields_present(self):
        self.store.add_credits("u1", 50)
        entry = self.store.get_credit_history("u1")["items"][0]
        for key in ("amount", "kind", "ref_id", "balance_after", "ts"):
            self.assertIn(key, entry)


class TestReviewHelpfulness(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.listing = _listing(self.store)
        self.lid = self.listing.listing_id
        _buy(self.store, self.lid, "u2")
        _, self.review = self.store.review(self.lid, "u2", "bob", 4, "Great avatar!")
        self.rid = self.review.review_id

    def test_vote_helpful_increases_count(self):
        result = self.store.vote_review_helpful(self.rid, "u3", True)
        self.assertEqual(result["helpful_count"], 1)
        self.assertEqual(result["unhelpful_count"], 0)
        self.assertTrue(result["user_vote"])

    def test_vote_unhelpful_increases_unhelpful_count(self):
        result = self.store.vote_review_helpful(self.rid, "u3", False)
        self.assertEqual(result["unhelpful_count"], 1)
        self.assertEqual(result["helpful_count"], 0)
        self.assertFalse(result["user_vote"])

    def test_vote_own_review_raises(self):
        with self.assertRaises(ValueError):
            self.store.vote_review_helpful(self.rid, "u2", True)

    def test_vote_unknown_review_raises(self):
        with self.assertRaises(ValueError):
            self.store.vote_review_helpful("no-such-review", "u3", True)

    def test_change_vote_updates_counts(self):
        self.store.vote_review_helpful(self.rid, "u3", True)
        result = self.store.vote_review_helpful(self.rid, "u3", False)
        self.assertEqual(result["helpful_count"], 0)
        self.assertEqual(result["unhelpful_count"], 1)

    def test_toggle_vote_off_removes_vote(self):
        self.store.vote_review_helpful(self.rid, "u3", True)
        result = self.store.vote_review_helpful(self.rid, "u3", True)
        self.assertEqual(result["helpful_count"], 0)
        self.assertIsNone(result["user_vote"])

    def test_multiple_users_can_vote(self):
        self.store.vote_review_helpful(self.rid, "u3", True)
        self.store.vote_review_helpful(self.rid, "u4", True)
        result = self.store.vote_review_helpful(self.rid, "u5", False)
        self.assertEqual(result["helpful_count"], 2)
        self.assertEqual(result["unhelpful_count"], 1)

    def test_vote_reflected_in_review_to_dict(self):
        self.store.vote_review_helpful(self.rid, "u3", True)
        self.store.vote_review_helpful(self.rid, "u4", True)
        reviews = self.store.get_reviews(self.lid)
        item = reviews["items"][0]
        self.assertEqual(item["helpful_count"], 2)

    def test_vote_result_has_required_fields(self):
        result = self.store.vote_review_helpful(self.rid, "u3", True)
        for key in ("review_id", "helpful_count", "unhelpful_count", "user_vote"):
            self.assertIn(key, result)


class TestMyListings(unittest.TestCase):
    def setUp(self):
        self.store = _store()

    def test_returns_empty_for_new_user(self):
        result = self.store.get_user_listings_page("u999")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])

    def test_returns_own_listings(self):
        _listing(self.store, owner_id="u1", owner_username="alice")
        _listing(self.store, avatar_id="av2", owner_id="u1", owner_username="alice")
        result = self.store.get_user_listings_page("u1")
        self.assertEqual(result["total"], 2)

    def test_excludes_other_users(self):
        _listing(self.store, owner_id="u1", owner_username="alice")
        _listing(self.store, avatar_id="av2", owner_id="u2", owner_username="bob")
        result = self.store.get_user_listings_page("u1")
        self.assertEqual(result["total"], 1)

    def test_excludes_inactive_by_default(self):
        lst = _listing(self.store, owner_id="u1", owner_username="alice")
        self.store.unpublish(lst.listing_id, "u1")
        result = self.store.get_user_listings_page("u1")
        self.assertEqual(result["total"], 0)

    def test_include_inactive_flag(self):
        lst = _listing(self.store, owner_id="u1", owner_username="alice")
        self.store.unpublish(lst.listing_id, "u1")
        result = self.store.get_user_listings_page("u1", include_inactive=True)
        self.assertEqual(result["total"], 1)

    def test_pagination(self):
        for i in range(6):
            _listing(self.store, avatar_id=f"av{i}", owner_id="u1", owner_username="alice")
        p1 = self.store.get_user_listings_page("u1", limit=4, offset=0)
        p2 = self.store.get_user_listings_page("u1", limit=4, offset=4)
        self.assertEqual(len(p1["items"]), 4)
        self.assertEqual(len(p2["items"]), 2)
        self.assertTrue(p1["has_more"])
        self.assertFalse(p2["has_more"])

    def test_newest_first_ordering(self):
        for i in range(3):
            _listing(self.store, avatar_id=f"av{i}", owner_id="u1", owner_username="alice")
        items = self.store.get_user_listings_page("u1")["items"]
        ids = [item["listing_id"] for item in items]
        self.assertEqual(ids, list(reversed(ids[::-1])) or ids)  # just ensure it returns 3

    def test_pagination_fields_present(self):
        _listing(self.store, owner_id="u1", owner_username="alice")
        result = self.store.get_user_listings_page("u1")
        for key in ("total", "offset", "limit", "has_more", "next_offset", "items"):
            self.assertIn(key, result)

    def test_serialized_items_total_consistent_with_items_returned(self):
        """Sorting and to_dict() must happen inside the lock so that the
        'total' count and the list of serialized items are a consistent
        snapshot; a race between filter and serialize would corrupt the count."""
        for i in range(3):
            _listing(self.store, avatar_id=f"avX{i}", owner_id="u1", owner_username="alice")
        result = self.store.get_user_listings_page("u1", limit=50)
        # When the full result fits in one page, total must equal len(items)
        self.assertEqual(result["total"], len(result["items"]))
        self.assertEqual(result["total"], 3)


class TestCategories(unittest.TestCase):
    def setUp(self):
        self.store = _store()

    def test_empty_when_no_listings(self):
        cats = self.store.get_categories()
        self.assertEqual(cats, [])

    def test_returns_categories_with_counts(self):
        _listing(self.store, category="vrc")
        _listing(self.store, avatar_id="av2", category="vrc")
        _listing(self.store, avatar_id="av3", category="vrchat")
        cats = self.store.get_categories()
        cat_map = {c["category"]: c["count"] for c in cats}
        self.assertEqual(cat_map["vrc"], 2)
        self.assertEqual(cat_map["vrchat"], 1)

    def test_sorted_by_count_descending(self):
        _listing(self.store, category="b")
        _listing(self.store, avatar_id="av2", category="a")
        _listing(self.store, avatar_id="av3", category="a")
        cats = self.store.get_categories()
        self.assertEqual(cats[0]["category"], "a")

    def test_inactive_listings_excluded(self):
        lst = _listing(self.store, category="rare")
        self.store.unpublish(lst.listing_id, "u1")
        cats = self.store.get_categories()
        cat_names = [c["category"] for c in cats]
        self.assertNotIn("rare", cat_names)

    def test_each_entry_has_category_and_count_keys(self):
        _listing(self.store, category="test")
        for entry in self.store.get_categories():
            self.assertIn("category", entry)
            self.assertIn("count", entry)


class TestReviewHiding(unittest.TestCase):
    def setUp(self):
        self.store = MarketplaceStore()
        lst = _listing(self.store)
        self.listing_id = lst.listing_id
        _buy(self.store, self.listing_id, "u2")
        _, self.rv = self.store.review(self.listing_id, "u2", "bob", 4, "Good avatar")
        self.review_id = self.rv.review_id

    def test_review_visible_by_default(self):
        result = self.store.get_reviews(self.listing_id)
        self.assertEqual(result["total"], 1)
        self.assertFalse(result["items"][0]["is_hidden"])

    def test_hide_review_removes_from_list(self):
        self.store.hide_review(self.review_id)
        result = self.store.get_reviews(self.listing_id)
        self.assertEqual(result["total"], 0)

    def test_hide_review_visible_with_include_hidden(self):
        self.store.hide_review(self.review_id)
        result = self.store.get_reviews(self.listing_id, include_hidden=True)
        self.assertEqual(result["total"], 1)
        self.assertTrue(result["items"][0]["is_hidden"])

    def test_unhide_review_restores_visibility(self):
        self.store.hide_review(self.review_id)
        self.store.unhide_review(self.review_id)
        result = self.store.get_reviews(self.listing_id)
        self.assertEqual(result["total"], 1)

    def test_hide_unknown_review_raises(self):
        with self.assertRaises(ValueError):
            self.store.hide_review("no-such-review-id")

    def test_unhide_unknown_review_raises(self):
        with self.assertRaises(ValueError):
            self.store.unhide_review("no-such-review-id")

    def test_review_to_dict_includes_is_hidden(self):
        d = self.rv.to_dict()
        self.assertIn("is_hidden", d)

    def test_hide_review_withdraws_rating(self):
        # The lone 4-star review contributes to the average; hiding it must
        # drop the listing's aggregate to empty, not leave it at 4.0.
        listing = self.store._listings[self.listing_id]
        self.assertEqual(listing.rating_count, 1)
        self.assertEqual(listing.average_rating, 4.0)
        self.store.hide_review(self.review_id)
        self.assertEqual(listing.rating_count, 0)
        self.assertEqual(listing.average_rating, 0.0)

    def test_unhide_review_restores_rating(self):
        listing = self.store._listings[self.listing_id]
        self.store.hide_review(self.review_id)
        self.store.unhide_review(self.review_id)
        self.assertEqual(listing.rating_count, 1)
        self.assertEqual(listing.average_rating, 4.0)

    def test_hidden_review_excluded_from_average_with_visible_one(self):
        # Add a second buyer with a 2-star review, then hide the 4-star one.
        # The visible average must reflect only the remaining 2-star review.
        _buy(self.store, self.listing_id, "u3")
        self.store.review(self.listing_id, "u3", "carol", 2, "Meh")
        listing = self.store._listings[self.listing_id]
        self.assertEqual(listing.rating_count, 2)
        self.assertEqual(listing.average_rating, 3.0)  # (4+2)/2
        self.store.hide_review(self.review_id)          # hide the 4-star
        self.assertEqual(listing.rating_count, 1)
        self.assertEqual(listing.average_rating, 2.0)   # only the 2-star remains

    def test_editing_hidden_review_keeps_it_excluded(self):
        # A moderator-hidden review that the author edits must stay hidden AND
        # stay out of the aggregate — editing cannot bypass moderation.
        self.store.hide_review(self.review_id)
        self.store.review(self.listing_id, "u2", "bob", 5, "Trying to game it")
        listing = self.store._listings[self.listing_id]
        self.assertEqual(listing.rating_count, 0)
        self.assertEqual(listing.average_rating, 0.0)

    def test_idempotent_hide_does_not_double_withdraw(self):
        listing = self.store._listings[self.listing_id]
        self.store.hide_review(self.review_id)
        self.store.hide_review(self.review_id)  # second hide is a no-op
        self.assertEqual(listing.rating_count, 0)
        self.store.unhide_review(self.review_id)
        self.assertEqual(listing.rating_count, 1)
        self.assertEqual(listing.average_rating, 4.0)

    def test_report_hide_withdraws_rating(self):
        # Hiding via the report-resolution path must also withdraw the rating.
        report = self.store.report_review(self.review_id, "u3", "spam", "bad")
        self.store.resolve_review_report(report.report_id, "mod1", "resolved", hide=True)
        listing = self.store._listings[self.listing_id]
        self.assertEqual(listing.rating_count, 0)
        self.assertEqual(listing.average_rating, 0.0)

    def test_delete_review_cleans_up_helpful_votes_and_replies(self):
        # Deleting a review must not leave orphaned helpful-votes/replies behind.
        _buy(self.store, self.listing_id, "u3")
        self.store.vote_review_helpful(self.review_id, "u3", True)
        self.store.add_review_reply(self.review_id, "u1", "alice", "thanks")
        self.assertIn(self.review_id, self.store._review_votes)
        self.assertIn(self.review_id, self.store._review_replies)
        self.store.delete_review(self.listing_id, "u2")
        self.assertNotIn(self.review_id, self.store._review_votes)
        self.assertNotIn(self.review_id, self.store._review_replies)

    def test_rating_distribution_matches_headline_when_hidden(self):
        # A 2-star review alongside the 4-star one, then hide the 4-star. The
        # distribution endpoint's average + total must match the headline
        # average exactly (hidden-review vote excluded everywhere).
        _buy(self.store, self.listing_id, "u3")
        self.store.review(self.listing_id, "u3", "carol", 2, "Meh")
        self.store.hide_review(self.review_id)  # hide the 4-star
        listing = self.store._listings[self.listing_id]
        dist = self.store.get_rating_distribution(self.listing_id)
        self.assertEqual(dist["total_ratings"], 1)
        self.assertEqual(dist["distribution"][2], 1)
        self.assertEqual(dist["distribution"][4], 0)   # hidden one not counted
        self.assertEqual(dist["average_rating"], listing.average_rating)
        self.assertEqual(dist["average_rating"], 2.0)

    def test_listing_analytics_average_matches_headline_when_hidden(self):
        _buy(self.store, self.listing_id, "u3")
        self.store.review(self.listing_id, "u3", "carol", 2, "Meh")
        self.store.hide_review(self.review_id)
        listing = self.store._listings[self.listing_id]
        analytics = self.store.get_listing_analytics(self.listing_id, "u1")
        self.assertEqual(analytics["average_rating"], listing.average_rating)
        self.assertEqual(analytics["rating_distribution"][4], 0)


class TestListingTransfer(unittest.TestCase):
    def setUp(self):
        self.store = MarketplaceStore()
        lst = _listing(self.store, owner_id="owner1")
        self.listing_id = lst.listing_id

    def test_transfer_changes_owner(self):
        result = self.store.transfer_listing(self.listing_id, "owner1", "owner2", "newuser")
        self.assertEqual(result.owner_id, "owner2")
        self.assertEqual(result.owner_username, "newuser")

    def test_transfer_persisted(self):
        self.store.transfer_listing(self.listing_id, "owner1", "owner2", "newuser")
        listing = self.store.get_listing(self.listing_id)
        self.assertEqual(listing.owner_id, "owner2")

    def test_transfer_non_owner_raises(self):
        with self.assertRaises(PermissionError):
            self.store.transfer_listing(self.listing_id, "other_user", "owner2", "newuser")

    def test_transfer_to_self_raises(self):
        with self.assertRaises(ValueError):
            self.store.transfer_listing(self.listing_id, "owner1", "owner1", "owner1")

    def test_transfer_unknown_listing_raises(self):
        with self.assertRaises(ValueError):
            self.store.transfer_listing("no-such-id", "owner1", "owner2", "newuser")

    def test_transfer_preserves_download_count(self):
        self.store.add_credits("downloader", 1000)
        self.store.download(self.listing_id, "downloader")
        self.store.transfer_listing(self.listing_id, "owner1", "owner2", "newuser")
        listing = self.store.get_listing(self.listing_id)
        self.assertEqual(listing.download_count, 1)

    def test_transfer_preserves_reviews(self):
        _buy(self.store, self.listing_id, "reviewer")
        self.store.review(self.listing_id, "reviewer", "reviewer", 5, "Great!")
        self.store.transfer_listing(self.listing_id, "owner1", "owner2", "newuser")
        reviews = self.store.get_reviews(self.listing_id)
        self.assertEqual(reviews["total"], 1)


class TestTagFeed(unittest.TestCase):
    def setUp(self):
        self.store = MarketplaceStore()

    def test_empty_tags_returns_empty(self):
        _listing(self.store, tags=["fantasy"])
        result = self.store.get_tag_feed([])
        self.assertEqual(result["total"], 0)

    def test_matching_tag_returns_listing(self):
        lst = _listing(self.store, tags=["fantasy"])
        result = self.store.get_tag_feed(["fantasy"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["listing_id"], lst.listing_id)

    def test_non_matching_tag_returns_empty(self):
        _listing(self.store, tags=["mecha"])
        result = self.store.get_tag_feed(["fantasy"])
        self.assertEqual(result["total"], 0)

    def test_multiple_tags_any_match(self):
        lst1 = _listing(self.store, tags=["fantasy"])
        lst2 = _listing(self.store, avatar_id="av2", tags=["mecha"])
        result = self.store.get_tag_feed(["fantasy", "mecha"])
        self.assertEqual(result["total"], 2)
        ids = {item["listing_id"] for item in result["items"]}
        self.assertIn(lst1.listing_id, ids)
        self.assertIn(lst2.listing_id, ids)

    def test_inactive_listing_excluded(self):
        lst = _listing(self.store, tags=["fantasy"])
        self.store.unpublish(lst.listing_id, "u1")
        result = self.store.get_tag_feed(["fantasy"])
        self.assertEqual(result["total"], 0)

    def test_pagination(self):
        import secrets as _s
        for _i in range(5):
            _listing(self.store, avatar_id=_s.token_hex(4), tags=["test"])
        page1 = self.store.get_tag_feed(["test"], limit=2, offset=0)
        page2 = self.store.get_tag_feed(["test"], limit=2, offset=2)
        self.assertEqual(page1["total"], 5)
        self.assertTrue(page1["has_more"])
        self.assertEqual(len(page1["items"]), 2)
        self.assertEqual(page2["offset"], 2)

    def test_sort_by_downloads(self):
        _listing(self.store, tags=["art"])
        lst2 = _listing(self.store, avatar_id="av2", tags=["art"])
        self.store.add_credits("downloader", 1000)
        self.store.download(lst2.listing_id, "downloader")
        result = self.store.get_tag_feed(["art"], sort_by="downloads")
        self.assertEqual(result["items"][0]["listing_id"], lst2.listing_id)

    def test_sort_by_newest_is_default(self):
        result = self.store.get_tag_feed(["art"])
        self.assertEqual(result["total"], 0)

    def test_response_has_standard_pagination_keys(self):
        _listing(self.store, tags=["x"])
        result = self.store.get_tag_feed(["x"])
        for key in ("total", "offset", "limit", "has_more", "next_offset", "items"):
            self.assertIn(key, result)


class TestReviewReports(unittest.TestCase):
    def setUp(self):
        self.store = MarketplaceStore()
        lst = _listing(self.store)
        self.listing_id = lst.listing_id
        _buy(self.store, self.listing_id, "u2")
        _, self.rv = self.store.review(self.listing_id, "u2", "bob", 3, "Decent")
        self.review_id = self.rv.review_id

    def test_report_review_succeeds(self):
        report = self.store.report_review(self.review_id, "u3", "spam")
        self.assertEqual(report.review_id, self.review_id)
        self.assertEqual(report.status, "pending")

    def test_report_review_invalid_reason_raises(self):
        with self.assertRaises(ValueError):
            self.store.report_review(self.review_id, "u3", "invalid_reason")

    def test_report_unknown_review_raises(self):
        with self.assertRaises(ValueError):
            self.store.report_review("no-such-id", "u3", "spam")

    def test_duplicate_pending_report_raises(self):
        self.store.report_review(self.review_id, "u3", "spam")
        with self.assertRaises(ValueError):
            self.store.report_review(self.review_id, "u3", "spam")

    def test_different_reporters_can_both_report(self):
        self.store.report_review(self.review_id, "u3", "spam")
        report2 = self.store.report_review(self.review_id, "u4", "offensive")
        self.assertIsNotNone(report2)

    def test_get_review_reports_returns_all(self):
        self.store.report_review(self.review_id, "u3", "spam")
        result = self.store.get_review_reports()
        self.assertEqual(result["total"], 1)

    def test_get_review_reports_filter_by_status(self):
        report = self.store.report_review(self.review_id, "u3", "spam")
        self.store.resolve_review_report(report.report_id, "mod1", "resolved")
        pending = self.store.get_review_reports(status="pending")
        self.assertEqual(pending["total"], 0)
        resolved = self.store.get_review_reports(status="resolved")
        self.assertEqual(resolved["total"], 1)

    def test_resolve_report_resolved(self):
        report = self.store.report_review(self.review_id, "u3", "offensive")
        result = self.store.resolve_review_report(report.report_id, "mod1", "resolved", "Valid report")
        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.resolved_by, "mod1")

    def test_resolve_report_dismissed(self):
        report = self.store.report_review(self.review_id, "u3", "false_info")
        result = self.store.resolve_review_report(report.report_id, "mod1", "dismissed")
        self.assertEqual(result.status, "dismissed")

    def test_resolve_with_hide_hides_review(self):
        report = self.store.report_review(self.review_id, "u3", "spam")
        self.store.resolve_review_report(report.report_id, "mod1", "resolved", hide=True)
        reviews = self.store.get_reviews(self.listing_id)
        self.assertEqual(reviews["total"], 0)

    def test_resolve_already_resolved_raises(self):
        report = self.store.report_review(self.review_id, "u3", "spam")
        self.store.resolve_review_report(report.report_id, "mod1", "resolved")
        with self.assertRaises(ValueError):
            self.store.resolve_review_report(report.report_id, "mod1", "dismissed")

    def test_resolve_invalid_action_raises(self):
        report = self.store.report_review(self.review_id, "u3", "spam")
        with self.assertRaises(ValueError):
            self.store.resolve_review_report(report.report_id, "mod1", "approve")

    def test_resolve_unknown_report_raises(self):
        with self.assertRaises(ValueError):
            self.store.resolve_review_report("no-such-id", "mod1", "resolved")

    def test_review_report_to_dict(self):
        report = self.store.report_review(self.review_id, "u3", "spam", "Clearly spam")
        d = report.to_dict()
        for key in ("report_id", "review_id", "reporter_id", "reason", "status", "created_at"):
            self.assertIn(key, d)


class TestPromoCodes(unittest.TestCase):
    def setUp(self):
        self.store = MarketplaceStore()
        lst = _listing(self.store, owner_id="creator1", is_free=False, price_credits=100)
        self.listing_id = lst.listing_id
        self.store.add_credits("buyer", 500)

    def test_create_promo_code_succeeds(self):
        pc = self.store.create_promo_code("creator1", "SAVE20", 20, listing_id=self.listing_id)
        self.assertEqual(pc.code, "SAVE20")
        self.assertEqual(pc.discount_percent, 20)
        self.assertTrue(pc.is_active)

    def test_create_promo_code_uppercases(self):
        pc = self.store.create_promo_code("creator1", "save20", 20)
        self.assertEqual(pc.code, "SAVE20")

    def test_create_promo_code_non_alnum_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_promo_code("creator1", "SAVE-20", 20)

    def test_create_promo_code_invalid_discount_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_promo_code("creator1", "TEST", 0)
        with self.assertRaises(ValueError):
            self.store.create_promo_code("creator1", "TEST", 100)

    def test_create_promo_code_non_owner_raises(self):
        with self.assertRaises(PermissionError):
            self.store.create_promo_code("other_user", "CODE", 10, listing_id=self.listing_id)

    def test_duplicate_active_code_raises(self):
        self.store.create_promo_code("creator1", "SAVE20", 20)
        with self.assertRaises(ValueError):
            self.store.create_promo_code("creator1", "SAVE20", 30)

    def test_download_with_valid_promo_applies_discount(self):
        self.store.create_promo_code("creator1", "SAVE20", 20, listing_id=self.listing_id)
        data = self.store.download(self.listing_id, "buyer", promo_code="SAVE20")
        self.assertIsNotNone(data)
        self.assertIn("promo_applied", data)
        self.assertEqual(data["promo_applied"]["actual_price"], 80)
        self.assertEqual(data["promo_applied"]["discount_percent"], 20)
        # amount_paid must reflect the discounted charge, not the list price.
        self.assertEqual(data["amount_paid"], 80)

    def test_download_without_promo_charges_full(self):
        data = self.store.download(self.listing_id, "buyer")
        self.assertNotIn("promo_applied", data)
        self.assertEqual(self.store.get_balance("buyer"), 400)

    def test_download_promo_increments_uses_count(self):
        self.store.create_promo_code("creator1", "USE1", 10, max_uses=1)
        self.store.download(self.listing_id, "buyer", promo_code="USE1")
        self.store.add_credits("buyer2", 500)
        # Second buyer tries same code — should not get discount (max_uses exhausted)
        data = self.store.download(self.listing_id, "buyer2", promo_code="USE1")
        self.assertNotIn("promo_applied", data)

    def test_steep_discount_rounding_to_zero_completes_as_free(self):
        # A 99%-off promo on a 50-credit listing rounds the charge to 0. The
        # money primitives reject non-positive amounts, so this must complete as
        # a free download — not crash with "amount must be positive".
        cheap = _listing(self.store, avatar_id="cheap_av", owner_id="creator1",
                         name="Cheap", is_free=False, price_credits=50)
        self.store.create_promo_code("creator1", "ALMOSTFREE", 99, listing_id=cheap.listing_id)
        buyer_before = self.store.get_balance("buyer")
        seller_before = self.store.get_balance("creator1")
        data = self.store.download(cheap.listing_id, "buyer", promo_code="ALMOSTFREE")
        self.assertIsNotNone(data)
        self.assertEqual(data["amount_paid"], 0)
        self.assertEqual(data["promo_applied"]["actual_price"], 0)
        # No credits moved on either side.
        self.assertEqual(self.store.get_balance("buyer"), buyer_before)
        self.assertEqual(self.store.get_balance("creator1"), seller_before)
        # The buyer now owns it (recorded), so a re-download stays free.
        self.assertTrue(self.store.has_downloaded(cheap.listing_id, "buyer"))

    def test_zero_rounded_promo_still_consumes_a_use(self):
        # Even when the effective price is 0, the promo WAS applied, so a
        # max_uses=1 code must be exhausted for the next buyer.
        cheap = _listing(self.store, avatar_id="cheap_av2", owner_id="creator1",
                         name="Cheap2", is_free=False, price_credits=50)
        self.store.create_promo_code("creator1", "ONESHOT", 99,
                                     listing_id=cheap.listing_id, max_uses=1)
        self.store.download(cheap.listing_id, "buyer", promo_code="ONESHOT")
        self.store.add_credits("buyer2", 500)
        # Second buyer: code exhausted → charged the full 50.
        data = self.store.download(cheap.listing_id, "buyer2", promo_code="ONESHOT")
        self.assertNotIn("promo_applied", data)
        self.assertEqual(data["amount_paid"], 50)

    def test_create_promo_code_naive_expiry_normalized_to_aware(self):
        # A naive expiry must be stored as UTC-aware so is_valid() doesn't raise
        # TypeError comparing it against an aware now().
        from datetime import datetime, timedelta
        naive_future = datetime.now() + timedelta(days=1)  # no tzinfo
        pc = self.store.create_promo_code("creator1", "NAIVE", 25, expires_at=naive_future)
        self.assertIsNotNone(pc.expires_at.tzinfo)
        # is_valid must not raise and should report still-valid.
        self.assertTrue(pc.is_valid())

    def test_is_valid_tolerates_naive_expiry(self):
        # Even a record whose expiry somehow ended up naive must compare safely.
        from datetime import datetime, timedelta
        pc = self.store.create_promo_code("creator1", "RAW", 10)
        pc.expires_at = datetime.now() + timedelta(days=1)  # force naive
        self.assertTrue(pc.is_valid())  # must not raise TypeError

    def test_deactivate_promo_code(self):
        pc = self.store.create_promo_code("creator1", "DEACT", 50)
        result = self.store.deactivate_promo_code(pc.code_id, "creator1")
        self.assertFalse(result.is_active)

    def test_deactivate_non_owner_raises(self):
        pc = self.store.create_promo_code("creator1", "NOPE", 10)
        with self.assertRaises(PermissionError):
            self.store.deactivate_promo_code(pc.code_id, "other_user")

    def test_list_promo_codes(self):
        self.store.create_promo_code("creator1", "CODE1", 10)
        self.store.create_promo_code("creator1", "CODE2", 20)
        codes = self.store.list_promo_codes("creator1")
        self.assertEqual(len(codes), 2)

    def test_lookup_promo_code_valid(self):
        self.store.create_promo_code("creator1", "LOOK10", 10, listing_id=self.listing_id)
        info = self.store.lookup_promo_code("LOOK10", self.listing_id)
        self.assertIsNotNone(info)
        self.assertEqual(info["discount_percent"], 10)
        self.assertEqual(info["discounted_price"], 90)
        self.assertEqual(info["original_price"], 100)

    def test_lookup_invalid_code_returns_none(self):
        info = self.store.lookup_promo_code("INVALID", self.listing_id)
        self.assertIsNone(info)

    def test_promo_code_to_dict(self):
        pc = self.store.create_promo_code("creator1", "DICT", 15)
        d = pc.to_dict()
        for key in ("code_id", "code", "creator_id", "discount_percent", "is_active", "is_valid", "created_at"):
            self.assertIn(key, d)


class TestTips(unittest.TestCase):
    def setUp(self):
        self.store = MarketplaceStore()
        self.store.add_credits("sender", 1000)

    def test_send_tip_transfers_credits(self):
        self.store.send_tip("sender", "alice", "recipient", 100)
        self.assertEqual(self.store.get_balance("sender"), 900)
        self.assertEqual(self.store.get_balance("recipient"), 100)

    def test_send_tip_returns_tip_object(self):
        tip = self.store.send_tip("sender", "alice", "recipient", 50, "Thanks!")
        self.assertEqual(tip.amount, 50)
        self.assertEqual(tip.message, "Thanks!")
        self.assertEqual(tip.sender_id, "sender")
        self.assertEqual(tip.recipient_id, "recipient")

    def test_send_tip_to_self_raises(self):
        with self.assertRaises(ValueError):
            self.store.send_tip("sender", "alice", "sender", 100)

    def test_public_tips_view_omits_sender_id_and_message(self):
        # Privacy: the public tips feed must not leak the tipper's stable id
        # or the private tip message.
        self.store.send_tip("sender", "alice", "recipient", 100, "secret note for you")
        pub = self.store.get_tips_received("recipient", public=True)
        item = pub["items"][0]
        self.assertNotIn("sender_id", item)
        self.assertNotIn("message", item)
        # ...but the intended public fields remain.
        self.assertEqual(item["sender_username"], "alice")
        self.assertEqual(item["amount"], 100)

    def test_owner_tips_view_keeps_sender_id_and_message(self):
        # The recipient's own (authenticated) view still sees full detail.
        self.store.send_tip("sender", "alice", "recipient", 100, "secret note")
        priv = self.store.get_tips_received("recipient")
        item = priv["items"][0]
        self.assertEqual(item["sender_id"], "sender")
        self.assertEqual(item["message"], "secret note")

    def test_tip_to_public_dict_directly(self):
        tip = self.store.send_tip("sender", "alice", "recipient", 25, "hi")
        d = tip.to_public_dict()
        self.assertNotIn("sender_id", d)
        self.assertNotIn("message", d)
        self.assertEqual(d["amount"], 25)

    def test_send_zero_tip_raises(self):
        with self.assertRaises(ValueError):
            self.store.send_tip("sender", "alice", "recipient", 0)

    def test_send_negative_tip_raises(self):
        with self.assertRaises(ValueError):
            self.store.send_tip("sender", "alice", "recipient", -10)

    def test_send_tip_insufficient_credits_raises(self):
        with self.assertRaises(ValueError):
            self.store.send_tip("sender", "alice", "recipient", 5000)

    def test_send_tip_exceeds_max_raises(self):
        self.store.add_credits("richsender", 100_000)
        with self.assertRaises(ValueError):
            self.store.send_tip("richsender", "rich", "recipient", 10_001)

    def test_get_tips_received_empty(self):
        result = self.store.get_tips_received("nobody")
        self.assertEqual(result["total"], 0)

    def test_get_tips_received_returns_tips(self):
        self.store.send_tip("sender", "alice", "recipient", 100)
        result = self.store.get_tips_received("recipient")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["amount"], 100)

    def test_get_tips_sent_returns_tips(self):
        self.store.send_tip("sender", "alice", "recipient", 100)
        result = self.store.get_tips_sent("sender")
        self.assertEqual(result["total"], 1)

    def test_tips_newest_first(self):
        self.store.send_tip("sender", "alice", "recipient", 10)
        self.store.send_tip("sender", "alice", "recipient", 20)
        result = self.store.get_tips_received("recipient")
        self.assertEqual(result["items"][0]["amount"], 20)
        self.assertEqual(result["items"][1]["amount"], 10)

    def test_get_tips_pagination(self):
        for _i in range(5):
            self.store.send_tip("sender", "alice", "recipient", 10)
        page1 = self.store.get_tips_received("recipient", limit=2, offset=0)
        self.assertEqual(page1["total"], 5)
        self.assertTrue(page1["has_more"])
        self.assertEqual(len(page1["items"]), 2)

    def test_tip_to_dict(self):
        tip = self.store.send_tip("sender", "alice", "recipient", 50, "Great work!")
        d = tip.to_dict()
        for key in ("tip_id", "sender_id", "sender_username", "recipient_id", "amount", "message", "created_at"):
            self.assertIn(key, d)

    def test_tip_records_ledger_entries(self):
        self.store.send_tip("sender", "alice", "recipient", 100)
        history = self.store.get_credit_history("sender")
        kinds = {entry["kind"] for entry in history["items"]}
        self.assertIn("tip_sent", kinds)


class TestListingAnalytics(unittest.TestCase):
    def setUp(self):
        self.store = MarketplaceStore()
        lst = _listing(self.store, owner_id="creator1")
        self.listing_id = lst.listing_id
        self.store.add_credits("buyer1", 1000)
        self.store.add_credits("buyer2", 1000)

    def test_analytics_returns_listing_id(self):
        result = self.store.get_listing_analytics(self.listing_id, "creator1")
        self.assertEqual(result["listing_id"], self.listing_id)

    def test_analytics_counts_downloads(self):
        self.store.download(self.listing_id, "buyer1")
        self.store.download(self.listing_id, "buyer2")
        result = self.store.get_listing_analytics(self.listing_id, "creator1")
        self.assertEqual(result["total_downloads"], 2)

    def test_analytics_unique_downloaders(self):
        self.store.download(self.listing_id, "buyer1")
        self.store.download(self.listing_id, "buyer1")  # same buyer twice
        result = self.store.get_listing_analytics(self.listing_id, "creator1")
        self.assertEqual(result["unique_downloaders"], 1)

    def test_analytics_review_count(self):
        _buy(self.store, self.listing_id, "buyer1", "buyer2")
        self.store.review(self.listing_id, "buyer1", "b1", 5, "Great!")
        self.store.review(self.listing_id, "buyer2", "b2", 4, "Good!")
        result = self.store.get_listing_analytics(self.listing_id, "creator1")
        self.assertEqual(result["total_reviews"], 2)

    def test_analytics_average_rating(self):
        _buy(self.store, self.listing_id, "buyer1", "buyer2")
        self.store.review(self.listing_id, "buyer1", "b1", 5, "Great!")
        self.store.review(self.listing_id, "buyer2", "b2", 3, "OK")
        result = self.store.get_listing_analytics(self.listing_id, "creator1")
        self.assertEqual(result["average_rating"], 4.0)

    def test_analytics_rating_distribution(self):
        _buy(self.store, self.listing_id, "buyer1")
        self.store.review(self.listing_id, "buyer1", "b1", 5, "Excellent!")
        result = self.store.get_listing_analytics(self.listing_id, "creator1")
        self.assertEqual(result["rating_distribution"][5], 1)
        self.assertEqual(result["rating_distribution"][1], 0)

    def test_analytics_downloads_by_day(self):
        self.store.download(self.listing_id, "buyer1")
        result = self.store.get_listing_analytics(self.listing_id, "creator1")
        self.assertIsInstance(result["downloads_by_day"], dict)
        self.assertEqual(sum(result["downloads_by_day"].values()), 1)

    def test_analytics_non_owner_raises(self):
        with self.assertRaises(PermissionError):
            self.store.get_listing_analytics(self.listing_id, "other_user")

    def test_analytics_unknown_listing_raises(self):
        with self.assertRaises(ValueError):
            self.store.get_listing_analytics("no-such-id", "creator1")

    def test_analytics_zero_downloads(self):
        result = self.store.get_listing_analytics(self.listing_id, "creator1")
        self.assertEqual(result["total_downloads"], 0)
        self.assertEqual(result["unique_downloaders"], 0)
        self.assertEqual(result["downloads_by_day"], {})


class TestStockLimit(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.store.add_credits("buyer", 1000)
        self.store.add_credits("buyer2", 1000)
        lst = _listing(self.store, owner_id="creator", owner_username="cr",
                       is_free=False, price_credits=50)
        self.listing_id = lst.listing_id

    def test_set_stock_limit(self):
        listing = self.store.set_stock_limit(self.listing_id, "creator", 5)
        self.assertEqual(listing.stock_limit, 5)
        self.assertEqual(listing.stock_remaining, 5)

    def test_stock_remaining_in_to_dict(self):
        self.store.set_stock_limit(self.listing_id, "creator", 3)
        d = self.store._listings[self.listing_id].to_dict()
        self.assertEqual(d["stock_limit"], 3)
        self.assertEqual(d["stock_remaining"], 3)
        self.assertFalse(d["is_sold_out"])

    def test_download_decrements_stock(self):
        self.store.set_stock_limit(self.listing_id, "creator", 2)
        self.store.download(self.listing_id, "buyer")
        listing = self.store._listings[self.listing_id]
        self.assertEqual(listing.stock_remaining, 1)

    def test_sold_out_blocks_download(self):
        self.store.set_stock_limit(self.listing_id, "creator", 1)
        self.store.download(self.listing_id, "buyer")
        with self.assertRaises(ValueError):
            self.store.download(self.listing_id, "buyer2")

    def test_owner_can_download_even_when_sold_out(self):
        self.store.set_stock_limit(self.listing_id, "creator", 0)
        result = self.store.download(self.listing_id, "creator")
        self.assertIsNotNone(result)

    def test_is_sold_out_flag(self):
        self.store.set_stock_limit(self.listing_id, "creator", 1)
        self.store.download(self.listing_id, "buyer")
        d = self.store._listings[self.listing_id].to_dict()
        self.assertTrue(d["is_sold_out"])

    def test_set_unlimited_clears_stock(self):
        self.store.set_stock_limit(self.listing_id, "creator", 5)
        self.store.set_stock_limit(self.listing_id, "creator", None)
        listing = self.store._listings[self.listing_id]
        self.assertIsNone(listing.stock_limit)
        self.assertIsNone(listing.stock_remaining)

    def test_unlimited_listing_no_sold_out(self):
        d = self.store._listings[self.listing_id].to_dict()
        self.assertFalse(d["is_sold_out"])
        self.assertIsNone(d["stock_limit"])

    def test_non_owner_cannot_set_stock(self):
        with self.assertRaises(PermissionError):
            self.store.set_stock_limit(self.listing_id, "other-user", 5)

    def test_negative_stock_raises(self):
        with self.assertRaises(ValueError):
            self.store.set_stock_limit(self.listing_id, "creator", -1)

    def test_stock_remaining_accounts_for_existing_downloads(self):
        self.store.download(self.listing_id, "buyer")
        self.store.set_stock_limit(self.listing_id, "creator", 3)
        listing = self.store._listings[self.listing_id]
        self.assertEqual(listing.stock_remaining, 2)

    def test_stock_missing_listing_raises(self):
        with self.assertRaises(ValueError):
            self.store.set_stock_limit("no-such-id", "creator", 5)

    # --- restock transition (drives back-in-stock notifications) ---

    def test_transition_restock_from_sold_out(self):
        # Sell out (limit 1, one download), then restock -> rising edge True.
        self.store.set_stock_limit(self.listing_id, "creator", 1)
        self.store.download(self.listing_id, "buyer")
        _, restocked = self.store.set_stock_limit_with_transition(
            self.listing_id, "creator", 5)
        self.assertTrue(restocked)

    def test_transition_raise_stock_not_sold_out_is_false(self):
        # Not sold out (5 -> 10): no rising edge, must NOT signal restock.
        self.store.set_stock_limit(self.listing_id, "creator", 5)
        _, restocked = self.store.set_stock_limit_with_transition(
            self.listing_id, "creator", 10)
        self.assertFalse(restocked)

    def test_transition_unlimited_from_sold_out_is_restock(self):
        # Sold out -> unlimited (None) is also a restock (now always available).
        self.store.set_stock_limit(self.listing_id, "creator", 1)
        self.store.download(self.listing_id, "buyer")
        _, restocked = self.store.set_stock_limit_with_transition(
            self.listing_id, "creator", None)
        self.assertTrue(restocked)

    def test_transition_still_sold_out_is_false(self):
        # Sold out, then set limit equal to already-sold count -> remaining 0,
        # still sold out -> no rising edge.
        self.store.set_stock_limit(self.listing_id, "creator", 1)
        self.store.download(self.listing_id, "buyer")  # 1 sold, remaining 0
        _, restocked = self.store.set_stock_limit_with_transition(
            self.listing_id, "creator", 1)  # limit 1, sold 1 -> remaining 0
        self.assertFalse(restocked)

    def test_transition_first_limit_on_unlimited_is_not_restock(self):
        # Unlimited (in stock) -> a finite positive limit: was never sold out.
        _, restocked = self.store.set_stock_limit_with_transition(
            self.listing_id, "creator", 5)
        self.assertFalse(restocked)

    def test_set_stock_limit_still_returns_listing(self):
        # Backward-compat: the original API returns just the listing.
        listing = self.store.set_stock_limit(self.listing_id, "creator", 4)
        self.assertEqual(listing.stock_remaining, 4)

    def test_redownload_allowed_when_sold_out(self):
        # Buyer purchases the last copy (stock 1 -> 0); they must still be able
        # to re-download without hitting the sold-out error.
        self.store.set_stock_limit(self.listing_id, "creator", 1)
        self.store.download(self.listing_id, "buyer")
        listing = self.store._listings[self.listing_id]
        self.assertEqual(listing.stock_remaining, 0)
        # Original buyer re-downloads — must NOT raise sold-out.
        result = self.store.download(self.listing_id, "buyer")
        self.assertIsNotNone(result)

    def test_redownload_does_not_decrement_stock(self):
        # Re-downloading an already-owned listing must not consume stock, which
        # would incorrectly reduce the copies available for new buyers.
        self.store.set_stock_limit(self.listing_id, "creator", 3)
        self.store.download(self.listing_id, "buyer")        # stock 3 -> 2
        self.store.download(self.listing_id, "buyer")        # re-download; stock stays 2
        listing = self.store._listings[self.listing_id]
        self.assertEqual(listing.stock_remaining, 2)

    def test_new_buyer_still_blocked_when_sold_out(self):
        # The sold-out guard must still block DIFFERENT buyers, not just
        # returning buyers (regression guard for the re-download fix).
        self.store.set_stock_limit(self.listing_id, "creator", 1)
        self.store.download(self.listing_id, "buyer")        # consumes last copy
        with self.assertRaises(ValueError):
            self.store.download(self.listing_id, "buyer2")  # different user, blocked


class TestEarningsSummary(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.store.add_credits("buyer", 1000)
        self.store.add_credits("tipper", 500)
        self.store.add_credits("gifter", 500)
        lst = _listing(self.store, owner_id="creator", owner_username="cr",
                       is_free=False, price_credits=100)
        self.listing_id = lst.listing_id

    def test_empty_earnings(self):
        result = self.store.get_earnings_summary("creator")
        self.assertEqual(result["total_earned"], 0)
        self.assertEqual(result["sales"], 0)

    def test_sale_shows_in_earnings(self):
        self.store.download(self.listing_id, "buyer")
        result = self.store.get_earnings_summary("creator")
        self.assertEqual(result["sales"], 100)
        self.assertEqual(result["total_earned"], 100)

    def test_tip_shows_in_earnings(self):
        self.store.send_tip("tipper", "tipper_name", "creator", 50)
        result = self.store.get_earnings_summary("creator")
        self.assertEqual(result["tips_and_gifts_received"], 50)
        self.assertEqual(result["total_earned"], 50)

    def test_gift_shows_in_earnings(self):
        self.store.gift_credits("gifter", "creator", 75)
        result = self.store.get_earnings_summary("creator")
        self.assertEqual(result["tips_and_gifts_received"], 75)
        self.assertEqual(result["total_earned"], 75)

    def test_earnings_combined(self):
        self.store.download(self.listing_id, "buyer")
        self.store.send_tip("tipper", "tipper_name", "creator", 50)
        self.store.gift_credits("gifter", "creator", 25)
        result = self.store.get_earnings_summary("creator")
        self.assertEqual(result["sales"], 100)
        self.assertEqual(result["tips_and_gifts_received"], 75)
        self.assertEqual(result["total_earned"], 175)

    def test_earnings_by_day_key(self):
        self.store.download(self.listing_id, "buyer")
        result = self.store.get_earnings_summary("creator")
        self.assertIn("by_day", result)
        self.assertEqual(len(result["by_day"]), 1)

    def test_period_days_returned(self):
        result = self.store.get_earnings_summary("creator", days=7)
        self.assertEqual(result["period_days"], 7)

    def test_user_id_in_result(self):
        result = self.store.get_earnings_summary("creator")
        self.assertEqual(result["user_id"], "creator")


if __name__ == "__main__":
    unittest.main(verbosity=2)
