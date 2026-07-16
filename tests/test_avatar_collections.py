"""Tests for main/avatar_collections.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from avatar_collections import Collection, CollectionStore, get_collection_store


class TestCreate(unittest.TestCase):
    def setUp(self):
        self.store = CollectionStore()

    def test_create_returns_collection(self):
        col = self.store.create("u1", "My Faves")
        self.assertIsInstance(col, Collection)
        self.assertEqual(col.name, "My Faves")
        self.assertEqual(col.owner_id, "u1")
        self.assertFalse(col.is_public)

    def test_create_public(self):
        col = self.store.create("u1", "Public", is_public=True)
        self.assertTrue(col.is_public)

    def test_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self.store.create("u1", "   ")

    def test_name_truncated(self):
        col = self.store.create("u1", "x" * 200)
        self.assertLessEqual(len(col.name), 100)

    def test_description_truncated(self):
        col = self.store.create("u1", "Name", description="y" * 800)
        self.assertLessEqual(len(col.description), 500)


class TestItems(unittest.TestCase):
    def setUp(self):
        self.store = CollectionStore()
        self.col = self.store.create("u1", "Collection")

    def test_add_item(self):
        col = self.store.add_item(self.col.collection_id, "u1", "listing-1")
        self.assertIn("listing-1", col.item_ids)

    def test_add_duplicate_idempotent(self):
        self.store.add_item(self.col.collection_id, "u1", "listing-1")
        col = self.store.add_item(self.col.collection_id, "u1", "listing-1")
        self.assertEqual(col.item_ids.count("listing-1"), 1)

    def test_readd_existing_item_at_capacity_is_noop(self):
        # Fill the collection to the cap, then re-add an item already present:
        # it must stay an idempotent no-op, not raise "max items".
        from avatar_collections import _MAX_ITEMS_PER_COLLECTION as CAP
        cid = self.col.collection_id
        for i in range(CAP):
            self.store.add_item(cid, "u1", f"item-{i}")
        # Collection is full; re-adding an existing item must not raise.
        col = self.store.add_item(cid, "u1", "item-0")
        self.assertEqual(len(col.item_ids), CAP)
        # But adding a genuinely new item at capacity still raises.
        with self.assertRaises(ValueError):
            self.store.add_item(cid, "u1", "overflow")

    def test_remove_item(self):
        self.store.add_item(self.col.collection_id, "u1", "listing-1")
        col = self.store.remove_item(self.col.collection_id, "u1", "listing-1")
        self.assertNotIn("listing-1", col.item_ids)

    def test_remove_missing_item_noop(self):
        col = self.store.remove_item(self.col.collection_id, "u1", "never-added")
        self.assertEqual(col.item_ids, [])

    def test_add_item_non_owner_raises(self):
        with self.assertRaises(PermissionError):
            self.store.add_item(self.col.collection_id, "u_other", "listing-1")

    def test_add_item_unknown_collection_raises(self):
        with self.assertRaises(ValueError):
            self.store.add_item("no-such-id", "u1", "listing-1")

    def test_item_count_in_dict(self):
        self.store.add_item(self.col.collection_id, "u1", "a")
        self.store.add_item(self.col.collection_id, "u1", "b")
        d = self.store.get(self.col.collection_id).to_dict()
        self.assertEqual(d["item_count"], 2)


class TestUpdateDelete(unittest.TestCase):
    def setUp(self):
        self.store = CollectionStore()
        self.col = self.store.create("u1", "Original")

    def test_update_name(self):
        col = self.store.update(self.col.collection_id, "u1", name="Renamed")
        self.assertEqual(col.name, "Renamed")

    def test_update_visibility(self):
        col = self.store.update(self.col.collection_id, "u1", is_public=True)
        self.assertTrue(col.is_public)

    def test_update_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self.store.update(self.col.collection_id, "u1", name="  ")

    def test_update_non_owner_raises(self):
        with self.assertRaises(PermissionError):
            self.store.update(self.col.collection_id, "u_other", name="Hacked")

    def test_delete_owner(self):
        ok = self.store.delete(self.col.collection_id, "u1")
        self.assertTrue(ok)
        self.assertIsNone(self.store.get(self.col.collection_id))

    def test_delete_non_owner_raises(self):
        with self.assertRaises(PermissionError):
            self.store.delete(self.col.collection_id, "u_other")

    def test_delete_unknown_returns_false(self):
        self.assertFalse(self.store.delete("no-such-id", "u1"))


class TestDeleteAllForOwner(unittest.TestCase):
    """delete_all_for_owner(): account-deletion cascade support."""

    def setUp(self):
        self.store = CollectionStore()

    def test_deletes_all_of_owners_collections(self):
        self.store.create("u1", "A")
        self.store.create("u1", "B")
        self.store.create("u1", "C")
        count = self.store.delete_all_for_owner("u1")
        self.assertEqual(count, 3)
        result = self.store.list_user_collections("u1", requester_id="u1")
        self.assertEqual(result["total"], 0)

    def test_does_not_touch_other_owners_collections(self):
        self.store.create("u1", "Mine")
        other = self.store.create("u2", "Theirs")
        self.store.delete_all_for_owner("u1")
        self.assertIsNotNone(self.store.get(other.collection_id))

    def test_unknown_owner_returns_zero(self):
        self.assertEqual(self.store.delete_all_for_owner("no-such-user"), 0)


class TestVisibility(unittest.TestCase):
    def setUp(self):
        self.store = CollectionStore()
        self.private = self.store.create("u1", "Private", is_public=False)
        self.public = self.store.create("u1", "Public", is_public=True)

    def test_list_own_shows_all(self):
        result = self.store.list_user_collections("u1", requester_id="u1")
        self.assertEqual(result["total"], 2)

    def test_list_other_shows_only_public(self):
        result = self.store.list_user_collections("u1", requester_id="u2")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["name"], "Public")

    def test_get_public_as_other(self):
        col = self.store.get_public(self.public.collection_id, "u2")
        self.assertIsNotNone(col)

    def test_get_private_as_other_returns_none(self):
        col = self.store.get_public(self.private.collection_id, "u2")
        self.assertIsNone(col)

    def test_get_private_as_owner(self):
        col = self.store.get_public(self.private.collection_id, "u1")
        self.assertIsNotNone(col)


class TestStats(unittest.TestCase):
    def test_stats(self):
        store = CollectionStore()
        c1 = store.create("u1", "A", is_public=True)
        store.create("u2", "B")
        store.add_item(c1.collection_id, "u1", "item-1")
        stats = store.stats()
        self.assertEqual(stats["total_collections"], 2)
        self.assertEqual(stats["public_collections"], 1)
        self.assertEqual(stats["total_items"], 1)


class TestSingleton(unittest.TestCase):
    def test_singleton(self):
        s1 = get_collection_store()
        s2 = get_collection_store()
        self.assertIs(s1, s2)


class TestBrowsePublic(unittest.TestCase):
    def setUp(self):
        from avatar_collections import CollectionStore
        self.store = CollectionStore()
        self.store.create("u1", "Public Alpha", "desc1", is_public=True)
        self.store.create("u1", "Public Beta", "desc2", is_public=True)
        self.store.create("u2", "Private One", "secret", is_public=False)

    def test_browse_returns_only_public(self):
        result = self.store.browse_public()
        self.assertEqual(result["total"], 2)

    def test_browse_excludes_private(self):
        result = self.store.browse_public()
        for item in result["items"]:
            self.assertTrue(item["is_public"])

    def test_browse_query_filter(self):
        result = self.store.browse_public(query="alpha")
        self.assertEqual(result["total"], 1)
        self.assertIn("Alpha", result["items"][0]["name"])

    def test_browse_query_case_insensitive(self):
        result = self.store.browse_public(query="BETA")
        self.assertEqual(result["total"], 1)

    def test_browse_empty_query_returns_all_public(self):
        result = self.store.browse_public(query="")
        self.assertEqual(result["total"], 2)

    def test_browse_pagination(self):
        p1 = self.store.browse_public(limit=1, offset=0)
        p2 = self.store.browse_public(limit=1, offset=1)
        self.assertEqual(len(p1["items"]), 1)
        self.assertEqual(len(p2["items"]), 1)
        self.assertTrue(p1["has_more"])
        self.assertFalse(p2["has_more"])

    def test_browse_has_pagination_fields(self):
        result = self.store.browse_public()
        for key in ("total", "offset", "limit", "has_more", "next_offset", "items"):
            self.assertIn(key, result)

    def test_browse_query_no_match_returns_empty(self):
        result = self.store.browse_public(query="zzznomatch")
        self.assertEqual(result["total"], 0)

    def test_browse_public_items_are_all_public(self):
        """Every item in browse_public results must have is_public=True serialized."""
        result = self.store.browse_public()
        for item in result["items"]:
            self.assertTrue(item["is_public"])


class TestListUserCollectionsPagination(unittest.TestCase):
    """list_user_collections() returns the standard pagination envelope."""

    def setUp(self):
        self.store = CollectionStore()
        for i in range(5):
            self.store.create("u1", f"Col {i}", is_public=(i % 2 == 0))

    def test_returns_pagination_envelope(self):
        result = self.store.list_user_collections("u1", requester_id="u1")
        for key in ("total", "offset", "limit", "has_more", "next_offset", "items"):
            self.assertIn(key, result)

    def test_total_reflects_visibility(self):
        own = self.store.list_user_collections("u1", requester_id="u1")
        other = self.store.list_user_collections("u1", requester_id="u2")
        self.assertEqual(own["total"], 5)
        self.assertLess(other["total"], 5)  # only public ones

    def test_pagination_slices_correctly(self):
        p1 = self.store.list_user_collections("u1", requester_id="u1", limit=2, offset=0)
        p2 = self.store.list_user_collections("u1", requester_id="u1", limit=2, offset=2)
        self.assertEqual(len(p1["items"]), 2)
        self.assertTrue(p1["has_more"])
        self.assertEqual(p2["next_offset"], 4)

    def test_has_more_false_on_last_page(self):
        result = self.store.list_user_collections("u1", requester_id="u1", limit=10, offset=0)
        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])


class _FakeListing:
    def __init__(self, listing_id, name, price, owner, is_active=True, stock=None):
        self.listing_id = listing_id
        self.name = name
        self.price_credits = price
        self.owner_id = owner
        self.is_active = is_active
        self.stock_remaining = stock


class _FakeMarketplace:
    def __init__(self, listings):
        import threading
        self._lock = threading.Lock()
        self._listings = {lst.listing_id: lst for lst in listings}


class TestGetItemsWithStatus(unittest.TestCase):
    """get_items_with_status() enriches item_ids with live marketplace data."""

    def setUp(self):
        self.store = CollectionStore()
        self.col = self.store.create("u1", "My Faves", is_public=True)
        self.store.add_item(self.col.collection_id, "u1", "L-active")
        self.store.add_item(self.col.collection_id, "u1", "L-soldout")
        self.store.add_item(self.col.collection_id, "u1", "L-delisted")
        self.mp = _FakeMarketplace([
            _FakeListing("L-active",   "Active Hat",   500, "seller1", is_active=True,  stock=None),
            _FakeListing("L-soldout",  "Sold-Out Cape", 300, "seller1", is_active=True,  stock=0),
            _FakeListing("L-delisted", "Gone Jacket",  200, "seller2", is_active=False),
        ])

    def _get(self, uid="u1", limit=50, offset=0):
        return self.store.get_items_with_status(
            self.col.collection_id, uid, self.mp, limit=limit, offset=offset
        )

    def test_returns_pagination_envelope(self):
        result = self._get()
        for key in ("total", "offset", "limit", "has_more", "next_offset", "items"):
            self.assertIn(key, result)
        self.assertEqual(result["total"], 3)

    def test_active_item_fields(self):
        result = self._get()
        items = {it["listing_id"]: it for it in result["items"]}
        a = items["L-active"]
        self.assertTrue(a["is_active"])
        self.assertFalse(a["delisted"])
        self.assertFalse(a["is_sold_out"])
        self.assertTrue(a["is_available"])
        self.assertEqual(a["current_price"], 500)
        self.assertEqual(a["listing_name"], "Active Hat")

    def test_soldout_item_fields(self):
        result = self._get()
        items = {it["listing_id"]: it for it in result["items"]}
        s = items["L-soldout"]
        self.assertTrue(s["is_active"])
        self.assertTrue(s["is_sold_out"])
        self.assertFalse(s["is_available"])
        self.assertFalse(s["delisted"])

    def test_delisted_item_fields(self):
        result = self._get()
        items = {it["listing_id"]: it for it in result["items"]}
        d = items["L-delisted"]
        self.assertFalse(d["is_active"])
        self.assertTrue(d["delisted"])
        self.assertIsNone(d["current_price"])
        self.assertIsNone(d["listing_name"])

    def test_pagination(self):
        p1 = self._get(limit=2, offset=0)
        p2 = self._get(limit=2, offset=2)
        self.assertEqual(len(p1["items"]), 2)
        self.assertTrue(p1["has_more"])
        self.assertEqual(len(p2["items"]), 1)
        self.assertFalse(p2["has_more"])

    def test_unknown_collection_raises_valueerror(self):
        with self.assertRaises(ValueError):
            self.store.get_items_with_status("no-such-id", "u1", self.mp)

    def test_private_collection_as_stranger_raises_permission(self):
        priv = self.store.create("u1", "Secret", is_public=False)
        with self.assertRaises(PermissionError):
            self.store.get_items_with_status(priv.collection_id, "u2", self.mp)

    def test_owner_can_see_private_collection_items(self):
        priv = self.store.create("u1", "Secret", is_public=False)
        self.store.add_item(priv.collection_id, "u1", "L-active")
        result = self.store.get_items_with_status(priv.collection_id, "u1", self.mp)
        self.assertEqual(result["total"], 1)


class TestGetPublicConsistency(unittest.TestCase):
    """get_public() must hold the lock when reading is_public / owner_id."""

    def setUp(self):
        self.store = CollectionStore()
        self.col = self.store.create("u1", "Collection", is_public=False)

    def test_get_public_private_as_owner_returns_collection(self):
        result = self.store.get_public(self.col.collection_id, "u1")
        self.assertIsNotNone(result)

    def test_get_public_private_as_stranger_returns_none(self):
        result = self.store.get_public(self.col.collection_id, "u2")
        self.assertIsNone(result)

    def test_get_public_after_visibility_change_reflects_update(self):
        """get_public() must see the current is_public value."""
        self.store.update(self.col.collection_id, "u1", is_public=True)
        result = self.store.get_public(self.col.collection_id, "u2")
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
