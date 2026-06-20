"""Tests for main/license_manager.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from license_manager import (
    LicenseKey,
    LicenseManager,
    LicenseStore,
    _generate_key,
    get_license_manager,
)


def _store() -> LicenseStore:
    return LicenseStore()


def _manager() -> LicenseManager:
    return LicenseManager(LicenseStore())


class TestGenerateKey(unittest.TestCase):
    def test_format(self):
        key = _generate_key()
        parts = key.split("-")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], "CCA")

    def test_uniqueness(self):
        keys = {_generate_key() for _ in range(100)}
        self.assertEqual(len(keys), 100)


class TestLicenseKey(unittest.TestCase):
    def _make_key(self, max_activations=None) -> LicenseKey:
        from license_manager import _generate_key
        return LicenseKey(
            key_id="kid1",
            key=_generate_key(),
            listing_id="lst1",
            owner_id="owner1",
            holder_id="buyer1",
            max_activations=max_activations,
        )

    def test_activation_count_starts_zero(self):
        lk = self._make_key()
        self.assertEqual(lk.activation_count(), 0)

    def test_can_activate_unlimited(self):
        lk = self._make_key(max_activations=None)
        self.assertTrue(lk.can_activate())

    def test_can_activate_with_limit(self):
        lk = self._make_key(max_activations=2)
        self.assertTrue(lk.can_activate())

    def test_cannot_activate_when_revoked(self):
        lk = self._make_key()
        lk.is_revoked = True
        self.assertFalse(lk.can_activate())

    def test_to_dict_fields(self):
        lk = self._make_key(max_activations=3)
        d = lk.to_dict()
        self.assertEqual(d["listing_id"], "lst1")
        self.assertEqual(d["max_activations"], 3)
        self.assertFalse(d["is_revoked"])
        self.assertEqual(d["activations"], [])


class TestLicenseStore(unittest.TestCase):
    def setUp(self):
        self.store = _store()

    def test_issue_key_creates_key(self):
        lk = self.store.issue_key("lst1", "owner1", "buyer1")
        self.assertEqual(lk.listing_id, "lst1")
        self.assertEqual(lk.holder_id, "buyer1")

    def test_issue_key_idempotent(self):
        lk1 = self.store.issue_key("lst1", "owner1", "buyer1")
        lk2 = self.store.issue_key("lst1", "owner1", "buyer1")
        self.assertEqual(lk1.key_id, lk2.key_id)

    def test_issue_key_different_buyer(self):
        lk1 = self.store.issue_key("lst1", "owner1", "buyer1")
        lk2 = self.store.issue_key("lst1", "owner1", "buyer2")
        self.assertNotEqual(lk1.key_id, lk2.key_id)

    def test_get_by_id(self):
        lk = self.store.issue_key("lst1", "owner1", "buyer1")
        fetched = self.store.get_by_id(lk.key_id)
        self.assertIsNotNone(fetched)

    def test_get_by_id_unknown_returns_none(self):
        self.assertIsNone(self.store.get_by_id("no-id"))

    def test_get_by_key_string(self):
        lk = self.store.issue_key("lst1", "owner1", "buyer1")
        fetched = self.store.get_by_key_string(lk.key)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.key_id, lk.key_id)

    def test_get_by_key_string_unknown_returns_none(self):
        self.assertIsNone(self.store.get_by_key_string("CCA-XXXXXXXX-XXXXXXXX-XXXXXXXX"))

    def test_activate_records_activation(self):
        lk = self.store.issue_key("lst1", "owner1", "buyer1")
        self.store.activate(lk.key_id, "buyer1", "VRChat world")
        self.assertEqual(lk.activation_count(), 1)

    def test_activate_wrong_holder_raises(self):
        lk = self.store.issue_key("lst1", "owner1", "buyer1")
        with self.assertRaises(PermissionError):
            self.store.activate(lk.key_id, "other-user")

    def test_activate_revoked_key_raises(self):
        lk = self.store.issue_key("lst1", "owner1", "buyer1")
        self.store.revoke(lk.key_id, "owner1")
        with self.assertRaises(ValueError):
            self.store.activate(lk.key_id, "buyer1")

    def test_activate_exceeds_limit_raises(self):
        lk = self.store.issue_key("lst1", "owner1", "buyer1", max_activations=1)
        self.store.activate(lk.key_id, "buyer1")
        with self.assertRaises(ValueError):
            self.store.activate(lk.key_id, "buyer1")

    def test_activate_unknown_key_raises(self):
        with self.assertRaises(ValueError):
            self.store.activate("no-id", "buyer1")

    def test_revoke_by_owner(self):
        lk = self.store.issue_key("lst1", "owner1", "buyer1")
        self.store.revoke(lk.key_id, "owner1", "abuse")
        self.assertTrue(lk.is_revoked)
        self.assertEqual(lk.revoked_by, "owner1")

    def test_revoke_by_non_owner_raises(self):
        lk = self.store.issue_key("lst1", "owner1", "buyer1")
        with self.assertRaises(PermissionError):
            self.store.revoke(lk.key_id, "stranger")

    def test_revoke_by_admin(self):
        lk = self.store.issue_key("lst1", "owner1", "buyer1")
        self.store.revoke(lk.key_id, "admin1", is_admin=True)
        self.assertTrue(lk.is_revoked)

    def test_revoke_unknown_key_raises(self):
        with self.assertRaises(ValueError):
            self.store.revoke("no-id", "owner1")

    def test_revoke_already_revoked_raises(self):
        lk = self.store.issue_key("lst1", "owner1", "buyer1")
        self.store.revoke(lk.key_id, "owner1", "first reason")
        with self.assertRaises(ValueError):
            self.store.revoke(lk.key_id, "owner1", "second reason")

    def test_admin_revoke_not_overwritten_by_owner(self):
        lk = self.store.issue_key("lst1", "owner1", "buyer1")
        self.store.revoke(lk.key_id, "admin99", reason="policy violation", is_admin=True)
        self.assertEqual(lk.revoked_by, "admin99")
        with self.assertRaises(ValueError):
            self.store.revoke(lk.key_id, "owner1", reason="owner override attempt")
        self.assertEqual(lk.revoked_by, "admin99")

    def test_verify_valid_key(self):
        lk = self.store.issue_key("lst1", "owner1", "buyer1")
        result = self.store.verify(lk.key)
        self.assertTrue(result["valid"])
        self.assertEqual(result["listing_id"], "lst1")

    def test_verify_unknown_key(self):
        result = self.store.verify("CCA-INVALID1-INVALID2-INVALID3")
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "not_found")

    def test_verify_revoked_key(self):
        lk = self.store.issue_key("lst1", "owner1", "buyer1")
        self.store.revoke(lk.key_id, "owner1")
        result = self.store.verify(lk.key)
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "revoked")

    def test_verify_reports_activation_count_consistently(self):
        # verify() reads the validity verdict and the activation_count under the
        # same lock, so the returned count reflects exactly the activations
        # recorded at verification time (a consistent snapshot).
        lk = self.store.issue_key("lst1", "owner1", "buyer1", max_activations=5)
        self.store.activate(lk.key_id, "buyer1")
        self.store.activate(lk.key_id, "buyer1")
        result = self.store.verify(lk.key)
        self.assertTrue(result["valid"])
        self.assertEqual(result["activation_count"], 2)
        self.assertEqual(result["max_activations"], 5)

    def test_get_holder_keys(self):
        lk1 = self.store.issue_key("lst1", "owner1", "buyer1")
        lk2 = self.store.issue_key("lst2", "owner1", "buyer1")
        result = self.store.get_holder_keys("buyer1")
        self.assertEqual(result["total"], 2)
        key_ids = {i["key_id"] for i in result["items"]}
        self.assertIn(lk1.key_id, key_ids)
        self.assertIn(lk2.key_id, key_ids)

    def test_get_holder_keys_pagination(self):
        for i in range(5):
            self.store.issue_key(f"lst{i}", "owner1", "buyer1")
        result = self.store.get_holder_keys("buyer1", limit=3, offset=0)
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["items"]), 3)
        self.assertTrue(result["has_more"])

    def test_get_listing_keys_by_owner(self):
        self.store.issue_key("lst1", "owner1", "buyer1")
        self.store.issue_key("lst1", "owner1", "buyer2")
        result = self.store.get_listing_keys("lst1", "owner1")
        self.assertEqual(result["total"], 2)

    def test_get_listing_keys_non_owner_raises(self):
        self.store.issue_key("lst1", "owner1", "buyer1")
        with self.assertRaises(PermissionError):
            self.store.get_listing_keys("lst1", "other-user")

    def test_get_listing_keys_unknown_listing_fails_closed(self):
        """Before any license is issued AND without register_listing_owner(),
        the internal owner record is absent. The permission check must fail
        closed (PermissionError) rather than silently succeeding with an empty
        response — otherwise any user can probe arbitrary listing IDs."""
        store = LicenseStore()
        with self.assertRaises(PermissionError):
            store.get_listing_keys("brand-new-listing", "anyone")

    def test_register_listing_owner_allows_real_owner_empty_list(self):
        """After register_listing_owner(), the real owner can see their empty
        key list (i.e. before any buyer has downloaded)."""
        store = LicenseStore()
        store.register_listing_owner("lst-new", "alice")
        result = store.get_listing_keys("lst-new", "alice")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])

    def test_register_listing_owner_still_blocks_non_owner(self):
        """register_listing_owner() must not allow anyone OTHER than the
        registered owner to access the listing keys."""
        store = LicenseStore()
        store.register_listing_owner("lst-new", "alice")
        with self.assertRaises(PermissionError):
            store.get_listing_keys("lst-new", "bob")

    def test_registered_owner_wins_over_key_embedded_owner(self):
        """When register_listing_owner() was called with the real owner,
        get_listing_keys() must use that record as the authority.  An
        incorrect owner_id embedded in a LicenseKey (e.g. due to a caller
        bug or payload tampering) must not override the registration and
        must not grant the wrong party access to buyer data."""
        store = LicenseStore()
        store.register_listing_owner("lst1", "real_owner")
        # Simulate a caller bug: issue_key called with wrong owner_id.
        store.issue_key("lst1", "wrong_owner", "buyer1")
        # Real owner can see their keys.
        result = store.get_listing_keys("lst1", "real_owner")
        self.assertEqual(result["total"], 1)
        # Attacker supplied as owner must be blocked.
        with self.assertRaises(PermissionError):
            store.get_listing_keys("lst1", "wrong_owner")


class TestLicenseManager(unittest.TestCase):
    def setUp(self):
        self.mgr = _manager()

    def test_issue_on_download(self):
        lk = self.mgr.issue_on_download("lst1", "owner1", "buyer1")
        self.assertEqual(lk.holder_id, "buyer1")

    def test_issue_idempotent(self):
        lk1 = self.mgr.issue_on_download("lst1", "owner1", "buyer1")
        lk2 = self.mgr.issue_on_download("lst1", "owner1", "buyer1")
        self.assertEqual(lk1.key_id, lk2.key_id)

    def test_activate_key_returns_dict(self):
        lk = self.mgr.issue_on_download("lst1", "owner1", "buyer1")
        result = self.mgr.activate_key(lk.key_id, "buyer1", "test env")
        self.assertIn("activations", result)
        self.assertEqual(len(result["activations"]), 1)

    def test_revoke_key_returns_dict(self):
        lk = self.mgr.issue_on_download("lst1", "owner1", "buyer1")
        result = self.mgr.revoke_key(lk.key_id, "owner1", "abuse")
        self.assertTrue(result["is_revoked"])

    def test_verify_key_valid(self):
        lk = self.mgr.issue_on_download("lst1", "owner1", "buyer1")
        result = self.mgr.verify_key(lk.key)
        self.assertTrue(result["valid"])

    def test_get_my_licenses(self):
        self.mgr.issue_on_download("lst1", "owner1", "buyer1")
        self.mgr.issue_on_download("lst2", "owner1", "buyer1")
        result = self.mgr.get_my_licenses("buyer1")
        self.assertEqual(result["total"], 2)


class TestLicenseSingleton(unittest.TestCase):
    def test_singleton(self):
        a = get_license_manager()
        b = get_license_manager()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
