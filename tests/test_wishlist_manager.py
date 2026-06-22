"""Tests for main/wishlist_manager.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from wishlist_manager import (
    WishlistItem,
    WishlistManager,
    WishlistStore,
    get_wishlist_manager,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeListing:
    def __init__(self, listing_id, price=200, active=True):
        self.listing_id = listing_id
        self.name = f"Avatar {listing_id}"
        self.price_credits = price
        self.is_active = active


class _FakeMP:
    def __init__(self):
        self._listings: dict = {}
        self._lock = __import__("threading").Lock()

    def add(self, lst: _FakeListing) -> None:
        self._listings[lst.listing_id] = lst


class _FakeNotifQueue:
    def __init__(self):
        self.sent: list = []

    def push(self, user_id, kind, title, body, payload=None):
        self.sent.append({"user_id": user_id, "kind": kind, "title": title, "body": body, "data": payload or {}})


def _make_manager() -> tuple:
    store = WishlistStore()
    mgr = WishlistManager(store)
    mp = _FakeMP()
    mp.add(_FakeListing("lst1", price=200))
    mp.add(_FakeListing("lst2", price=0))
    return mgr, mp


# ---------------------------------------------------------------------------
# WishlistItem
# ---------------------------------------------------------------------------

class TestWishlistItem(unittest.TestCase):
    def test_to_dict(self):
        item = WishlistItem("lst1", 200, "Cool Avatar")
        d = item.to_dict()
        self.assertEqual(d["listing_id"], "lst1")
        self.assertEqual(d["snapshot_price"], 200)
        self.assertIn("added_at", d)


# ---------------------------------------------------------------------------
# WishlistStore
# ---------------------------------------------------------------------------

class TestWishlistStore(unittest.TestCase):
    def setUp(self):
        self.store = WishlistStore()

    def test_add_item(self):
        item = self.store.add("u1", "lst1", 200, "Avatar 1")
        self.assertEqual(item.listing_id, "lst1")

    def test_add_idempotent(self):
        item1 = self.store.add("u1", "lst1", 200, "Avatar 1")
        item2 = self.store.add("u1", "lst1", 150, "Avatar 1 cheaper")
        self.assertIs(item1, item2)
        self.assertEqual(item1.snapshot_price, 200)  # unchanged

    def test_remove_existing(self):
        self.store.add("u1", "lst1", 200, "Av1")
        result = self.store.remove("u1", "lst1")
        self.assertTrue(result)
        self.assertFalse(self.store.contains("u1", "lst1"))

    def test_remove_nonexistent(self):
        result = self.store.remove("u1", "nonexistent")
        self.assertFalse(result)

    def test_contains(self):
        self.store.add("u1", "lst1", 200, "Av1")
        self.assertTrue(self.store.contains("u1", "lst1"))
        self.assertFalse(self.store.contains("u1", "lst2"))

    def test_get_wishlist_empty(self):
        result = self.store.get_wishlist("u1")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])

    def test_get_wishlist_pagination(self):
        for i in range(5):
            self.store.add("u1", f"lst{i}", 100, f"Av{i}")
        result = self.store.get_wishlist("u1", limit=3, offset=0)
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["items"]), 3)
        self.assertTrue(result["has_more"])

    def test_get_wishlisters(self):
        self.store.add("u1", "lst1", 200, "Av1")
        self.store.add("u2", "lst1", 200, "Av1")
        wishlisters = self.store.get_wishlisters("lst1")
        self.assertIn("u1", wishlisters)
        self.assertIn("u2", wishlisters)

    def test_check_price_drops(self):
        self.store.add("u1", "lst1", 200, "Av1")
        self.store.add("u2", "lst1", 200, "Av1")
        drops = self.store.check_price_drops("lst1", 150)
        self.assertEqual(len(drops), 2)
        for d in drops:
            self.assertEqual(d["old_price"], 200)
            self.assertEqual(d["new_price"], 150)

    def test_check_price_drops_no_drop(self):
        self.store.add("u1", "lst1", 200, "Av1")
        drops = self.store.check_price_drops("lst1", 250)
        self.assertEqual(drops, [])

    def test_check_price_drops_same_price(self):
        self.store.add("u1", "lst1", 200, "Av1")
        drops = self.store.check_price_drops("lst1", 200)
        self.assertEqual(drops, [])

    def test_clear(self):
        self.store.add("u1", "lst1", 200, "Av1")
        self.store.add("u1", "lst2", 100, "Av2")
        removed = self.store.clear("u1")
        self.assertEqual(removed, 2)
        self.assertEqual(self.store.get_wishlist("u1")["total"], 0)

    def test_max_items_raises(self):
        from wishlist_manager import _MAX_WISHLIST_ITEMS
        for i in range(_MAX_WISHLIST_ITEMS):
            self.store.add("u1", f"lst{i}", 100, f"Av{i}")
        with self.assertRaises(ValueError):
            self.store.add("u1", "overflow", 100, "Over")


# ---------------------------------------------------------------------------
# WishlistManager
# ---------------------------------------------------------------------------

class TestWishlistManager(unittest.TestCase):
    def setUp(self):
        self.mgr, self.mp = _make_manager()

    def test_add_item(self):
        item = self.mgr.add_item("u1", "lst1", self.mp)
        self.assertEqual(item["listing_id"], "lst1")
        self.assertEqual(item["snapshot_price"], 200)

    def test_add_inactive_listing_raises(self):
        self.mp.add(_FakeListing("inactive", active=False))
        with self.assertRaises(ValueError):
            self.mgr.add_item("u1", "inactive", self.mp)

    def test_add_unknown_listing_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.add_item("u1", "no-such-listing", self.mp)

    def test_remove_item(self):
        self.mgr.add_item("u1", "lst1", self.mp)
        result = self.mgr.remove_item("u1", "lst1")
        self.assertTrue(result)

    def test_contains(self):
        self.mgr.add_item("u1", "lst1", self.mp)
        self.assertTrue(self.mgr.contains("u1", "lst1"))
        self.assertFalse(self.mgr.contains("u1", "lst2"))

    def test_get_wishlist(self):
        self.mgr.add_item("u1", "lst1", self.mp)
        self.mgr.add_item("u1", "lst2", self.mp)
        result = self.mgr.get_wishlist("u1")
        self.assertEqual(result["total"], 2)

    def test_get_wishlisters_count(self):
        self.mgr.add_item("u1", "lst1", self.mp)
        self.mgr.add_item("u2", "lst1", self.mp)
        self.assertEqual(self.mgr.get_wishlisters_count("lst1"), 2)

    def test_price_drop_notification(self):
        self.mgr.add_item("u1", "lst1", self.mp)
        queue = _FakeNotifQueue()
        self.mp._listings["lst1"].price_credits = 100  # drop from 200 to 100
        count = self.mgr.check_and_notify_price_drops("lst1", 100, queue)
        self.assertEqual(count, 1)
        self.assertEqual(queue.sent[0]["kind"], "price_drop")
        self.assertEqual(queue.sent[0]["data"]["new_price"], 100)

    def test_no_notification_when_price_unchanged(self):
        self.mgr.add_item("u1", "lst1", self.mp)
        queue = _FakeNotifQueue()
        count = self.mgr.check_and_notify_price_drops("lst1", 200, queue)
        self.assertEqual(count, 0)
        self.assertEqual(queue.sent, [])

    def test_same_drop_not_renotified(self):
        # Once a drop to a given price is notified, re-running the check at that
        # same price must NOT notify again (the snapshot advanced to it).
        self.mgr.add_item("u1", "lst1", self.mp)
        queue = _FakeNotifQueue()
        self.assertEqual(self.mgr.check_and_notify_price_drops("lst1", 100, queue), 1)
        self.assertEqual(self.mgr.check_and_notify_price_drops("lst1", 100, queue), 0)
        self.assertEqual(len(queue.sent), 1)

    def test_further_drop_notifies_again(self):
        # A new, lower price after a prior drop notifies once more.
        self.mgr.add_item("u1", "lst1", self.mp)
        queue = _FakeNotifQueue()
        self.assertEqual(self.mgr.check_and_notify_price_drops("lst1", 100, queue), 1)
        self.assertEqual(self.mgr.check_and_notify_price_drops("lst1", 80, queue), 1)
        self.assertEqual(len(queue.sent), 2)
        self.assertEqual(queue.sent[1]["data"]["old_price"], 100)
        self.assertEqual(queue.sent[1]["data"]["new_price"], 80)

    def test_clear_wishlist(self):
        self.mgr.add_item("u1", "lst1", self.mp)
        removed = self.mgr.clear_wishlist("u1")
        self.assertEqual(removed, 1)
        self.assertEqual(self.mgr.get_wishlist("u1")["total"], 0)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestWishlistSingleton(unittest.TestCase):
    def test_singleton(self):
        a = get_wishlist_manager()
        b = get_wishlist_manager()
        self.assertIs(a, b)


class TestRestockNotification(unittest.TestCase):
    """Back-in-stock alerts: when a sold-out wishlisted listing is restocked,
    every wishlister is notified (the sibling of price-drop alerts)."""

    def setUp(self):
        self.mgr, self.mp = _make_manager()

    def test_restock_notifies_all_wishlisters(self):
        self.mgr.add_item("u1", "lst1", self.mp)
        self.mgr.add_item("u2", "lst1", self.mp)
        queue = _FakeNotifQueue()
        count = self.mgr.check_and_notify_restock("lst1", "Cool Avatar", queue)
        self.assertEqual(count, 2)
        self.assertEqual({s["kind"] for s in queue.sent}, {"back_in_stock"})
        self.assertEqual({s["user_id"] for s in queue.sent}, {"u1", "u2"})
        self.assertEqual(queue.sent[0]["data"]["listing_id"], "lst1")
        self.assertIn("Cool Avatar", queue.sent[0]["body"])

    def test_no_wishlisters_sends_nothing(self):
        queue = _FakeNotifQueue()
        count = self.mgr.check_and_notify_restock("lst1", "Cool Avatar", queue)
        self.assertEqual(count, 0)
        self.assertEqual(queue.sent, [])

    def test_only_wishlisters_of_that_listing_notified(self):
        self.mgr.add_item("u1", "lst1", self.mp)
        self.mgr.add_item("u2", "lst2", self.mp)  # different listing
        queue = _FakeNotifQueue()
        count = self.mgr.check_and_notify_restock("lst1", "Cool Avatar", queue)
        self.assertEqual(count, 1)
        self.assertEqual(queue.sent[0]["user_id"], "u1")

    def test_push_failure_is_tolerated(self):
        self.mgr.add_item("u1", "lst1", self.mp)
        self.mgr.add_item("u2", "lst1", self.mp)

        class _FlakyQueue:
            def __init__(self):
                self.calls = 0

            def push(self, *a, **k):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("queue down")

        q = _FlakyQueue()
        count = self.mgr.check_and_notify_restock("lst1", "Cool Avatar", q)
        self.assertEqual(count, 1)
        self.assertEqual(q.calls, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
