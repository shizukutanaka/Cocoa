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


class TestVisibility(unittest.TestCase):
    def setUp(self):
        self.store = CollectionStore()
        self.private = self.store.create("u1", "Private", is_public=False)
        self.public = self.store.create("u1", "Public", is_public=True)

    def test_list_own_shows_all(self):
        cols = self.store.list_user_collections("u1", requester_id="u1")
        self.assertEqual(len(cols), 2)

    def test_list_other_shows_only_public(self):
        cols = self.store.list_user_collections("u1", requester_id="u2")
        self.assertEqual(len(cols), 1)
        self.assertEqual(cols[0]["name"], "Public")

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
