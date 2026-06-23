"""Tests for main/bundle_manager.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bundle_manager import Bundle, BundleManager, BundleStore, get_bundle_manager
from cart_manager import CartManager
from refund_manager import RefundManager

# ---------------------------------------------------------------------------
# Fake marketplace for testing purchase_bundle
# ---------------------------------------------------------------------------

class _FakeListing:
    def __init__(self, listing_id, owner_id, price=100, is_free=False, active=True):
        self.listing_id = listing_id
        self.owner_id = owner_id
        self.name = f"Avatar {listing_id}"
        self.price_credits = price
        self.is_free = is_free
        self.is_active = active
        self.download_count = 0
        self.stock_remaining = None
        self.updated_at = None


class _FakeMP:
    def __init__(self):
        self._listings: dict = {}
        self._credits: dict = {}
        self._download_log: list = []
        self._ledger: list = []
        self._lock = __import__("threading").Lock()

    def add(self, listing: _FakeListing) -> None:
        self._listings[listing.listing_id] = listing

    def _record_download_locked(self, listing_id, user_id, ts, amount_paid=0):
        self._download_log.append((listing_id, user_id, ts, amount_paid))

    def get_downloaded_ids(self, user_id):
        return {lid for lid, did, _, _ap in self._download_log if did == user_id}

    def _has_downloaded_locked(self, user_id, listing_id):
        return any(lid == listing_id and did == user_id for lid, did, _, _ap in self._download_log)

    def _append_ledger(self, user_id, amount, kind, ref_id=None, balance_after=0):
        self._ledger.append({"user_id": user_id, "amount": amount, "kind": kind})

    def _credit_locked(self, user_id, amount, kind, ref_id=""):
        if amount <= 0:
            raise ValueError("amount must be positive")
        self._credits[user_id] = self._credits.get(user_id, 0) + amount
        self._append_ledger(user_id, amount, kind, ref_id=ref_id)
        return self._credits[user_id]

    def _debit_locked(self, user_id, amount, kind, ref_id=""):
        if amount <= 0:
            raise ValueError("amount must be positive")
        balance = self._credits.get(user_id, 0)
        if balance < amount:
            raise ValueError(f"残高不足 (残高: {balance}, 必要: {amount})")
        self._credits[user_id] = balance - amount
        self._append_ledger(user_id, -amount, kind, ref_id=ref_id)
        return self._credits[user_id]

    # Public audited API (used by the refund workflow)
    def get_balance(self, user_id):
        return self._credits.get(user_id, 0)

    def credit(self, user_id, amount, kind, ref_id=""):
        return self._credit_locked(user_id, amount, kind, ref_id)

    def debit(self, user_id, amount, kind, ref_id=""):
        return self._debit_locked(user_id, amount, kind, ref_id)


def _make_mgr() -> tuple:
    store = BundleStore()
    mgr = BundleManager(store)
    mp = _FakeMP()
    mp._credits["buyer"] = 10_000
    mp._credits["creator"] = 0
    lst1 = _FakeListing("lst1", "creator", price=200)
    lst2 = _FakeListing("lst2", "creator", price=100)
    lst3 = _FakeListing("lst3", "creator", price=300)
    mp.add(lst1)
    mp.add(lst2)
    mp.add(lst3)
    return mgr, mp


# ---------------------------------------------------------------------------
# Bundle dataclass
# ---------------------------------------------------------------------------

class TestBundle(unittest.TestCase):
    def test_to_dict(self):
        b = Bundle("bid", "cr", "creator", "Pack", "desc", ["l1", "l2"], 20)
        d = b.to_dict()
        self.assertEqual(d["bundle_id"], "bid")
        self.assertEqual(d["listing_count"], 2)
        self.assertEqual(d["discount_percent"], 20)
        self.assertTrue(d["is_active"])


# ---------------------------------------------------------------------------
# BundleStore
# ---------------------------------------------------------------------------

class TestBundleStore(unittest.TestCase):
    def setUp(self):
        self.store = BundleStore()

    def test_create_bundle(self):
        b = self.store.create("cr", "creator", "Pack", "desc", ["l1", "l2"], 20)
        self.assertEqual(b.creator_id, "cr")
        self.assertEqual(len(b.listing_ids), 2)

    def test_get_bundle(self):
        b = self.store.create("cr", "creator", "Pack", "", ["l1", "l2"], 10)
        fetched = self.store.get(b.bundle_id)
        self.assertIsNotNone(fetched)

    def test_get_unknown_returns_none(self):
        self.assertIsNone(self.store.get("no-id"))

    def test_update_name(self):
        b = self.store.create("cr", "creator", "Old", "", ["l1", "l2"], 10)
        updated = self.store.update(b.bundle_id, "cr", name="New")
        self.assertEqual(updated.name, "New")

    def test_update_non_owner_raises(self):
        b = self.store.create("cr", "creator", "Pack", "", ["l1", "l2"], 10)
        with self.assertRaises(PermissionError):
            self.store.update(b.bundle_id, "other")

    def test_update_unknown_raises(self):
        with self.assertRaises(ValueError):
            self.store.update("no-id", "cr")

    def test_set_active(self):
        b = self.store.create("cr", "creator", "Pack", "", ["l1", "l2"], 10)
        self.store.set_active(b.bundle_id, "cr", False)
        self.assertFalse(b.is_active)

    def test_set_active_non_owner_raises(self):
        b = self.store.create("cr", "creator", "Pack", "", ["l1", "l2"], 10)
        with self.assertRaises(PermissionError):
            self.store.set_active(b.bundle_id, "stranger", False)

    def test_delete_bundle(self):
        b = self.store.create("cr", "creator", "Pack", "", ["l1", "l2"], 10)
        self.store.delete(b.bundle_id, "cr")
        self.assertIsNone(self.store.get(b.bundle_id))

    def test_delete_non_owner_raises(self):
        b = self.store.create("cr", "creator", "Pack", "", ["l1", "l2"], 10)
        with self.assertRaises(PermissionError):
            self.store.delete(b.bundle_id, "stranger")

    def test_list_by_creator(self):
        self.store.create("cr", "creator", "Pack1", "", ["l1", "l2"], 10)
        self.store.create("cr", "creator", "Pack2", "", ["l3", "l4"], 20)
        result = self.store.list_by_creator("cr")
        self.assertEqual(result["total"], 2)

    def test_list_active_only(self):
        b = self.store.create("cr", "creator", "Pack1", "", ["l1", "l2"], 10)
        self.store.create("cr", "creator", "Pack2", "", ["l3", "l4"], 20)
        self.store.set_active(b.bundle_id, "cr", False)
        result = self.store.list_by_creator("cr", include_inactive=False)
        self.assertEqual(result["total"], 1)


# ---------------------------------------------------------------------------
# BundleManager — create/update/delete
# ---------------------------------------------------------------------------

class TestBundleManagerCRUD(unittest.TestCase):
    def setUp(self):
        self.mgr, self.mp = _make_mgr()

    def test_create_valid_bundle(self):
        d = self.mgr.create_bundle("creator", "cr", "Pack", "", ["lst1", "lst2"], 20, self.mp)
        self.assertEqual(d["discount_percent"], 20)
        self.assertEqual(d["listing_count"], 2)

    def test_create_too_few_listings_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.create_bundle("creator", "cr", "Pack", "", ["lst1"], 10, self.mp)

    def test_create_too_many_listings_raises(self):
        for i in range(21):
            self.mp.add(_FakeListing(f"extra{i}", "creator"))
        listing_ids = [f"extra{i}" for i in range(21)]
        with self.assertRaises(ValueError):
            self.mgr.create_bundle("creator", "cr", "Pack", "", listing_ids, 10, self.mp)

    def test_create_invalid_discount_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.create_bundle("creator", "cr", "Pack", "", ["lst1", "lst2"], 95, self.mp)

    def test_create_other_owners_listing_raises(self):
        self.mp.add(_FakeListing("other_lst", "other_owner"))
        with self.assertRaises(PermissionError):
            self.mgr.create_bundle("creator", "cr", "Pack", "", ["lst1", "other_lst"], 10, self.mp)

    def test_create_duplicate_listing_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.create_bundle("creator", "cr", "Pack", "", ["lst1", "lst1"], 10, self.mp)

    def test_update_bundle(self):
        b = self.mgr.create_bundle("creator", "cr", "Pack", "", ["lst1", "lst2"], 20, self.mp)
        updated = self.mgr.update_bundle(b["bundle_id"], "creator", self.mp, name="New Pack")
        self.assertEqual(updated["name"], "New Pack")

    def test_deactivate_bundle(self):
        b = self.mgr.create_bundle("creator", "cr", "Pack", "", ["lst1", "lst2"], 10, self.mp)
        result = self.mgr.deactivate_bundle(b["bundle_id"], "creator")
        self.assertFalse(result["is_active"])

    def test_activate_bundle(self):
        b = self.mgr.create_bundle("creator", "cr", "Pack", "", ["lst1", "lst2"], 10, self.mp)
        self.mgr.deactivate_bundle(b["bundle_id"], "creator")
        result = self.mgr.activate_bundle(b["bundle_id"], "creator")
        self.assertTrue(result["is_active"])

    def test_delete_bundle(self):
        b = self.mgr.create_bundle("creator", "cr", "Pack", "", ["lst1", "lst2"], 10, self.mp)
        self.mgr.delete_bundle(b["bundle_id"], "creator")
        self.assertIsNone(self.mgr.get_bundle(b["bundle_id"]))


# ---------------------------------------------------------------------------
# BundleManager — purchase
# ---------------------------------------------------------------------------

class TestBundlePurchase(unittest.TestCase):
    def setUp(self):
        self.mgr, self.mp = _make_mgr()
        b = self.mgr.create_bundle("creator", "cr", "Pack", "", ["lst1", "lst2", "lst3"], 50, self.mp)
        self.bundle_id = b["bundle_id"]

    def test_purchase_deducts_credits(self):
        initial = self.mp._credits["buyer"]
        result = self.mgr.purchase_bundle(self.bundle_id, "buyer", self.mp)
        charged = result["total_charged"]
        self.assertEqual(self.mp._credits["buyer"], initial - charged)

    def test_purchase_applies_discount(self):
        result = self.mgr.purchase_bundle(self.bundle_id, "buyer", self.mp)
        for item in result["purchased"]:
            if item["unit_price"] > 0:
                self.assertEqual(item["discount_percent"], 50)
                self.assertLess(item["final_price"], item["unit_price"])

    def test_purchase_records_downloads(self):
        self.mgr.purchase_bundle(self.bundle_id, "buyer", self.mp)
        downloaded = [(lid, did) for lid, did, _, _ap in self.mp._download_log if did == "buyer"]
        self.assertEqual(len(downloaded), 3)

    def test_purchase_records_amount_paid(self):
        # The download log must record what the buyer actually paid per item
        # (the discounted final_price), so creator revenue analytics is accurate.
        result = self.mgr.purchase_bundle(self.bundle_id, "buyer", self.mp)
        paid_by_listing = {p["listing_id"]: p["final_price"] for p in result["purchased"]}
        logged = {lid: ap for lid, did, _, ap in self.mp._download_log if did == "buyer"}
        self.assertEqual(logged, paid_by_listing)
        # And the recorded amounts must be the discounted prices, not zero.
        self.assertTrue(all(ap > 0 for ap in logged.values()))

    def test_purchase_inactive_bundle_raises(self):
        self.mgr.deactivate_bundle(self.bundle_id, "creator")
        with self.assertRaises(ValueError):
            self.mgr.purchase_bundle(self.bundle_id, "buyer", self.mp)

    def test_creator_cannot_buy_own_bundle(self):
        with self.assertRaises(ValueError):
            self.mgr.purchase_bundle(self.bundle_id, "creator", self.mp)

    def test_already_owned_items_skipped(self):
        # Simulate buyer already downloaded lst1
        self.mp._download_log.append(("lst1", "buyer", __import__("datetime").datetime.now(), 0))
        result = self.mgr.purchase_bundle(self.bundle_id, "buyer", self.mp)
        skipped_ids = [s["listing_id"] for s in result["skipped"]]
        self.assertIn("lst1", skipped_ids)

    def test_purchase_unknown_bundle_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.purchase_bundle("no-bundle", "buyer", self.mp)

    def test_purchase_insufficient_credits(self):
        self.mp._credits["buyer"] = 0
        result = self.mgr.purchase_bundle(self.bundle_id, "buyer", self.mp)
        # All paid items should be skipped due to insufficient credits
        for item in result["skipped"]:
            self.assertIn(item["reason"], ["insufficient_credits", "already_owned"])

    def test_sold_out_listing_skipped_not_oversold(self):
        # Regression: a stock-exhausted listing must not be sold via a bundle.
        self.mp._listings["lst1"].stock_remaining = 0
        buyer_before = self.mp._credits["buyer"]
        result = self.mgr.purchase_bundle(self.bundle_id, "buyer", self.mp)
        skipped = {s["listing_id"]: s["reason"] for s in result["skipped"]}
        self.assertEqual(skipped.get("lst1"), "sold_out")
        # lst1 was never charged for or download-logged
        purchased_ids = [p["listing_id"] for p in result["purchased"]]
        self.assertNotIn("lst1", purchased_ids)
        logged = [lid for lid, did, _, _ap in self.mp._download_log if lid == "lst1"]
        self.assertEqual(logged, [])
        # Buyer charged only for the other two items, not the sold-out one
        self.assertEqual(self.mp._credits["buyer"], buyer_before - result["total_charged"])

    def test_limited_stock_decrements_via_bundle(self):
        # A listing with remaining stock still sells and decrements.
        self.mp._listings["lst2"].stock_remaining = 5
        self.mgr.purchase_bundle(self.bundle_id, "buyer", self.mp)
        self.assertEqual(self.mp._listings["lst2"].stock_remaining, 4)

    def test_no_order_without_cart_manager(self):
        result = self.mgr.purchase_bundle(self.bundle_id, "buyer", self.mp)
        self.assertIsNone(result["order_id"])

    def test_order_emitted_with_cart_manager(self):
        cart = CartManager()
        result = self.mgr.purchase_bundle(self.bundle_id, "buyer", self.mp, cart)
        self.assertIsNotNone(result["order_id"])
        order = cart.store.get_order(result["order_id"])
        self.assertIsNotNone(order)
        self.assertEqual(order.user_id, "buyer")
        self.assertEqual(order.total_credits, result["total_charged"])
        # Each order item carries its seller so a refund can claw back.
        self.assertTrue(all(i.owner_id == "creator" for i in order.items))

    def test_purchase_result_exposes_notification_fields(self):
        """Each purchased item must carry owner_id, listing_id, and name so the
        API layer can dispatch per-creator new_download notifications and issue
        license keys — mirrors the same contract checked for cart checkout."""
        result = self.mgr.purchase_bundle(self.bundle_id, "buyer", self.mp)
        for item in result["purchased"]:
            for field in ("listing_id", "owner_id", "name"):
                self.assertIn(field, item, f"bundle purchase item missing '{field}'")
        owner_ids = {i["owner_id"] for i in result["purchased"]}
        self.assertIn("creator", owner_ids)

    def test_bundle_purchase_is_refundable_end_to_end(self):
        cart = CartManager()
        refunds = RefundManager()
        creator_before = self.mp._credits["creator"]
        buyer_before = self.mp._credits["buyer"]

        result = self.mgr.purchase_bundle(self.bundle_id, "buyer", self.mp, cart)
        order_id = result["order_id"]
        charged = result["total_charged"]
        self.assertEqual(self.mp._credits["creator"], creator_before + charged)

        req = refunds.request_refund("buyer", order_id, "changed my mind", cart)
        admin = {"sub": "admin1", "role": "admin"}
        refunds.approve_refund(admin, req["request_id"], self.mp, cart)

        # Buyer made whole; creator's proceeds clawed back; order marked refunded.
        self.assertEqual(self.mp._credits["buyer"], buyer_before)
        self.assertEqual(self.mp._credits["creator"], creator_before)
        self.assertEqual(cart.store.get_order(order_id).status, "refunded")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestBundleSingleton(unittest.TestCase):
    def test_singleton(self):
        a = get_bundle_manager()
        b = get_bundle_manager()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
