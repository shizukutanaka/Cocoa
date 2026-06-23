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


class _FakeListing:
    """Minimal listing-like object for testing _listing_matches."""
    def __init__(self, name="Test Avatar", category="vrc", tags=None,
                 is_free=True, price_credits=0, platform="",
                 description="", owner_username=""):
        self.name = name
        self.category = category
        self.tags = tags or []
        self.is_free = is_free
        self.price_credits = price_credits
        self.platform = platform
        self.description = description
        self.owner_username = owner_username


class TestSavedSearchNotify(unittest.TestCase):
    def setUp(self):
        self.store = SavedSearchStore()

    def test_notify_on_match_default_false(self):
        ss = self.store.create("u1", "My Search")
        self.assertFalse(ss.notify_on_match)

    def test_set_notify_on_match_enables(self):
        ss = self.store.create("u1", "Alert Search")
        updated = self.store.set_notify_on_match("u1", ss.search_id, True)
        self.assertIsNotNone(updated)
        self.assertTrue(updated.notify_on_match)

    def test_set_notify_on_match_wrong_user_returns_none(self):
        ss = self.store.create("u1", "My Search")
        result = self.store.set_notify_on_match("u2", ss.search_id, True)
        self.assertIsNone(result)

    def test_find_matches_empty_if_none_enabled(self):
        self.store.create("u1", "Search", query="fantasy")
        listing = _FakeListing(name="Fantasy Avatar")
        matches = self.store.find_matches(listing)
        self.assertEqual(matches, [])

    def test_find_matches_query_hit(self):
        ss = self.store.create("u1", "Fantasy", query="fantasy")
        self.store.set_notify_on_match("u1", ss.search_id, True)
        listing = _FakeListing(name="Cool Fantasy Avatar")
        matches = self.store.find_matches(listing)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].search_id, ss.search_id)

    def test_find_matches_query_miss(self):
        ss = self.store.create("u1", "Mecha", query="mecha")
        self.store.set_notify_on_match("u1", ss.search_id, True)
        listing = _FakeListing(name="Fantasy Avatar")
        matches = self.store.find_matches(listing)
        self.assertEqual(matches, [])

    def test_find_matches_category_filter(self):
        ss = self.store.create("u1", "VRC Only", filters={"category": "vrc"})
        self.store.set_notify_on_match("u1", ss.search_id, True)
        hit = _FakeListing(category="vrc")
        miss = _FakeListing(category="vrchat")
        self.assertEqual(len(self.store.find_matches(hit)), 1)
        self.assertEqual(len(self.store.find_matches(miss)), 0)

    def test_find_matches_category_is_case_insensitive(self):
        # Must match the marketplace search()'s case-insensitive category compare,
        # otherwise a saved search that returns live results would silently never
        # notify on a casing mismatch.
        ss = self.store.create("u1", "VRChat", filters={"category": "VRChat"})
        self.store.set_notify_on_match("u1", ss.search_id, True)
        listing = _FakeListing(category="vrchat")
        self.assertEqual(len(self.store.find_matches(listing)), 1)

    def test_find_matches_tags_filter(self):
        """Tag matching uses OR semantics, consistent with marketplace.search().
        A listing that has ANY of the saved tags triggers a notification;
        it does NOT need to have ALL of them."""
        ss = self.store.create("u1", "Cute or VRC", filters={"tags": ["cute", "vrc"]})
        self.store.set_notify_on_match("u1", ss.search_id, True)
        hit_both = _FakeListing(tags=["cute", "vrc", "anime"])  # both tags present
        hit_one = _FakeListing(tags=["cute"])                   # only one tag — should still match
        miss = _FakeListing(tags=["anime"])                     # neither tag
        self.assertEqual(len(self.store.find_matches(hit_both)), 1)
        self.assertEqual(len(self.store.find_matches(hit_one)), 1)
        self.assertEqual(len(self.store.find_matches(miss)), 0)

    def test_find_matches_is_free_filter(self):
        ss = self.store.create("u1", "Free Only", filters={"is_free": True})
        self.store.set_notify_on_match("u1", ss.search_id, True)
        hit = _FakeListing(is_free=True)
        miss = _FakeListing(is_free=False, price_credits=100)
        self.assertEqual(len(self.store.find_matches(hit)), 1)
        self.assertEqual(len(self.store.find_matches(miss)), 0)

    def test_find_matches_price_range_filter(self):
        ss = self.store.create("u1", "Budget", filters={"min_price": 50, "max_price": 150})
        self.store.set_notify_on_match("u1", ss.search_id, True)
        hit = _FakeListing(is_free=False, price_credits=100)
        too_cheap = _FakeListing(is_free=False, price_credits=30)
        too_expensive = _FakeListing(is_free=False, price_credits=200)
        self.assertEqual(len(self.store.find_matches(hit)), 1)
        self.assertEqual(len(self.store.find_matches(too_cheap)), 0)
        self.assertEqual(len(self.store.find_matches(too_expensive)), 0)

    def test_to_dict_includes_notify_on_match(self):
        ss = self.store.create("u1", "Search")
        d = ss.to_dict()
        self.assertIn("notify_on_match", d)
        self.assertFalse(d["notify_on_match"])

    def test_find_matches_platform_filter_hit(self):
        ss = self.store.create("u1", "VRC Only", filters={"platform": "vrchat"})
        self.store.set_notify_on_match("u1", ss.search_id, True)
        hit = _FakeListing(platform="vrchat")
        miss = _FakeListing(platform="neos")
        self.assertEqual(len(self.store.find_matches(hit)), 1)
        self.assertEqual(len(self.store.find_matches(miss)), 0)

    def test_find_matches_platform_filter_case_insensitive(self):
        ss = self.store.create("u1", "VRChat", filters={"platform": "VRChat"})
        self.store.set_notify_on_match("u1", ss.search_id, True)
        listing = _FakeListing(platform="vrchat")
        self.assertEqual(len(self.store.find_matches(listing)), 1)

    def test_find_matches_platform_no_attribute_excluded(self):
        """Listing with no platform attribute is excluded when a platform filter is set."""
        ss = self.store.create("u1", "VRC Only", filters={"platform": "vrchat"})
        self.store.set_notify_on_match("u1", ss.search_id, True)

        class _NoPlatform:
            name = "Test"
            category = "vrc"
            tags = []
            is_free = True
            price_credits = 0

        self.assertEqual(len(self.store.find_matches(_NoPlatform())), 0)

    def test_find_matches_no_platform_filter_matches_any_platform(self):
        """No platform filter must not exclude listings with any platform value."""
        ss = self.store.create("u1", "All Platforms", query="test")
        self.store.set_notify_on_match("u1", ss.search_id, True)
        for p in ("vrchat", "neos", "ar", ""):
            listing = _FakeListing(name="test avatar", platform=p)
            self.assertEqual(len(self.store.find_matches(listing)), 1,
                             f"platform={p!r} should match when no platform filter is set")

    def test_find_matches_sees_updated_query(self):
        """find_matches() must read the current query/filters atomically."""
        ss = self.store.create("u1", "Fantasy", query="fantasy")
        self.store.set_notify_on_match("u1", ss.search_id, True)
        # Update the query before matching — find_matches must use the new query
        self.store.update("u1", ss.search_id, query="mecha")
        listing = _FakeListing(name="Cool Fantasy Avatar")
        # Old query "fantasy" would match; updated query "mecha" must not
        matches = self.store.find_matches(listing)
        self.assertEqual(matches, [])

    def test_find_matches_platform_with_marketplace_listing(self):
        """Platform filter must work against real MarketplaceListing objects, not
        just the _FakeListing stub.  Before MarketplaceListing gained a platform
        field, getattr fell back to '' and all platform filters were silent-ignored."""
        from avatar_marketplace import MarketplaceStore
        mp = MarketplaceStore()
        listing = mp.publish(
            "av_vrchat", "creator1", "alice", "VRChat Avatar", "for vrchat",
            ["vrc"], "vrc", {}, platform="vrchat",
        )
        ss = self.store.create("u1", "VRChat Only", filters={"platform": "vrchat"})
        self.store.set_notify_on_match("u1", ss.search_id, True)
        matches = self.store.find_matches(listing)
        self.assertEqual(len(matches), 1)
        # A listing published for a different platform must not match
        other = mp.publish(
            "av_neos", "creator1", "alice", "Neos Avatar", "for neos",
            ["neos"], "neos", {}, platform="neos",
        )
        self.assertEqual(len(self.store.find_matches(other)), 0)

    def test_find_matches_query_in_description(self):
        """A query that appears only in the listing description must match.
        marketplace.search() checks name AND description; find_matches() must
        be consistent — otherwise a saved search silently misses listings that
        the live search actually returns."""
        ss = self.store.create("u1", "Cute Desc", query="unique_desc_word")
        self.store.set_notify_on_match("u1", ss.search_id, True)
        hit = _FakeListing(name="Generic Avatar", description="unique_desc_word inside the blurb")
        miss = _FakeListing(name="Generic Avatar", description="no match here")
        self.assertEqual(len(self.store.find_matches(hit)), 1)
        self.assertEqual(len(self.store.find_matches(miss)), 0)

    def test_find_matches_query_in_owner_username(self):
        """A query matching owner_username must also notify — marketplace.search()
        includes owner_username in its fulltext check."""
        ss = self.store.create("u1", "Creator Search", query="famous_creator")
        self.store.set_notify_on_match("u1", ss.search_id, True)
        hit = _FakeListing(name="Some Avatar", owner_username="famous_creator")
        miss = _FakeListing(name="Some Avatar", owner_username="unknown_creator")
        self.assertEqual(len(self.store.find_matches(hit)), 1)
        self.assertEqual(len(self.store.find_matches(miss)), 0)

    def test_find_matches_description_missing_attribute_safe(self):
        """Listings without a description attribute (legacy stubs) must not raise."""

        class _NoDesc:
            name = "Test"
            category = "vrc"
            tags = []
            is_free = True
            price_credits = 0
            platform = ""

        ss = self.store.create("u1", "Search", query="test")
        self.store.set_notify_on_match("u1", ss.search_id, True)
        self.assertEqual(len(self.store.find_matches(_NoDesc())), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
