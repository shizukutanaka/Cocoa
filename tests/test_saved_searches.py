"""Tests for main/saved_searches.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from saved_searches import SavedSearch, SavedSearchStore, get_saved_search_store


class TestSavedSearchCreate(unittest.TestCase):
    def setUp(self):
        self.store = SavedSearchStore()

    def test_create_returns_saved_search(self):
        ss = self.store.create("u1", "My Search", query="cat", filters={"category": "animal"})
        self.assertIsInstance(ss, SavedSearch)

    def test_create_stores_all_fields(self):
        ss = self.store.create("u1", "My Search", query="cat", filters={"category": "animal"})
        self.assertEqual(ss.user_id, "u1")
        self.assertEqual(ss.name, "My Search")
        self.assertEqual(ss.query, "cat")
        self.assertEqual(ss.filters["category"], "animal")

    def test_search_id_is_unique(self):
        a = self.store.create("u1", "A")
        b = self.store.create("u1", "B")
        self.assertNotEqual(a.search_id, b.search_id)

    def test_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self.store.create("u1", "  ")

    def test_empty_filters_default(self):
        ss = self.store.create("u1", "No Filters")
        self.assertEqual(ss.filters, {})

    def test_last_used_initially_none(self):
        ss = self.store.create("u1", "Test")
        self.assertIsNone(ss.last_used)

    def test_use_count_initially_zero(self):
        ss = self.store.create("u1", "Test")
        self.assertEqual(ss.use_count, 0)


class TestSavedSearchList(unittest.TestCase):
    def setUp(self):
        self.store = SavedSearchStore()

    def test_list_empty_for_new_user(self):
        self.assertEqual(self.store.list("u1"), [])

    def test_list_returns_own_searches(self):
        self.store.create("u1", "Search A")
        self.store.create("u1", "Search B")
        searches = self.store.list("u1")
        self.assertEqual(len(searches), 2)

    def test_list_does_not_include_other_users(self):
        self.store.create("u1", "Alice Search")
        self.store.create("u2", "Bob Search")
        alice_searches = self.store.list("u1")
        self.assertEqual(len(alice_searches), 1)
        self.assertEqual(alice_searches[0].name, "Alice Search")


class TestSavedSearchDelete(unittest.TestCase):
    def setUp(self):
        self.store = SavedSearchStore()
        self.ss = self.store.create("u1", "Test Search")

    def test_delete_own_search(self):
        ok = self.store.delete("u1", self.ss.search_id)
        self.assertTrue(ok)
        self.assertEqual(self.store.list("u1"), [])

    def test_delete_nonexistent_returns_false(self):
        self.assertFalse(self.store.delete("u1", "no-such-id"))

    def test_delete_another_users_search_fails(self):
        ok = self.store.delete("u2", self.ss.search_id)
        self.assertFalse(ok)
        self.assertEqual(len(self.store.list("u1")), 1)


class TestSavedSearchRecordUse(unittest.TestCase):
    def setUp(self):
        self.store = SavedSearchStore()
        self.ss = self.store.create("u1", "Frequent Search")

    def test_record_use_updates_last_used(self):
        ok = self.store.record_use("u1", self.ss.search_id)
        self.assertTrue(ok)
        self.assertIsNotNone(self.ss.last_used)

    def test_record_use_increments_count(self):
        self.store.record_use("u1", self.ss.search_id)
        self.store.record_use("u1", self.ss.search_id)
        self.assertEqual(self.ss.use_count, 2)

    def test_record_use_wrong_user_returns_false(self):
        self.assertFalse(self.store.record_use("u2", self.ss.search_id))


class TestSavedSearchUpdate(unittest.TestCase):
    def setUp(self):
        self.store = SavedSearchStore()
        self.ss = self.store.create("u1", "Old Name", query="old query")

    def test_update_name(self):
        updated = self.store.update("u1", self.ss.search_id, name="New Name")
        self.assertIsNotNone(updated)
        self.assertEqual(updated.name, "New Name")

    def test_update_query(self):
        updated = self.store.update("u1", self.ss.search_id, query="new query")
        self.assertEqual(updated.query, "new query")

    def test_update_filters(self):
        updated = self.store.update("u1", self.ss.search_id, filters={"platform": "vrc"})
        self.assertEqual(updated.filters["platform"], "vrc")

    def test_update_wrong_user_returns_none(self):
        result = self.store.update("u2", self.ss.search_id, name="Hacked")
        self.assertIsNone(result)

    def test_update_nonexistent_returns_none(self):
        result = self.store.update("u1", "no-such-id", name="X")
        self.assertIsNone(result)


class TestSavedSearchQuota(unittest.TestCase):
    def test_quota_enforced(self):
        store = SavedSearchStore(max_per_user=2)
        store.create("u1", "A")
        store.create("u1", "B")
        with self.assertRaises(ValueError):
            store.create("u1", "C")

    def test_quota_per_user_independent(self):
        store = SavedSearchStore(max_per_user=1)
        store.create("u1", "Alice A")
        store.create("u2", "Bob A")  # should not raise
        self.assertEqual(len(store.list("u2")), 1)


class TestSavedSearchToDict(unittest.TestCase):
    def setUp(self):
        self.store = SavedSearchStore()
        self.ss = self.store.create("u1", "Dict Test", query="dog", filters={"tags": ["cute"]})

    def test_to_dict_fields(self):
        d = self.ss.to_dict()
        for key in ("search_id", "user_id", "name", "query", "filters", "created_at", "last_used", "use_count"):
            self.assertIn(key, d)

    def test_to_dict_no_internal_state(self):
        d = self.ss.to_dict()
        self.assertNotIn("_lock", d)


class TestSavedSearchStats(unittest.TestCase):
    def setUp(self):
        self.store = SavedSearchStore(max_per_user=10)

    def test_stats_total(self):
        self.store.create("u1", "A")
        self.store.create("u1", "B")
        s = self.store.stats("u1")
        self.assertEqual(s["total"], 2)

    def test_stats_max_allowed(self):
        s = self.store.stats("u1")
        self.assertEqual(s["max_allowed"], 10)


class TestSavedSearchSingleton(unittest.TestCase):
    def test_singleton(self):
        a = get_saved_search_store()
        b = get_saved_search_store()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
