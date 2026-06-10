"""Tests for main/avatar_marketplace.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from avatar_marketplace import MarketplaceStore


def _store():
    return MarketplaceStore()


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

    def test_download_inactive_listing_returns_none(self):
        store = _store()
        listing = _listing(store)
        store.unpublish(listing.listing_id, "u1")
        self.assertIsNone(store.download(listing.listing_id, "u2"))

    def test_download_unknown_listing(self):
        store = _store()
        self.assertIsNone(store.download("bad-id", "u1"))


class TestRating(unittest.TestCase):
    def test_rate_valid(self):
        store = _store()
        listing = _listing(store)
        avg = store.rate(listing.listing_id, "u2", 4)
        self.assertEqual(avg, 4.0)

    def test_rate_updates_average(self):
        store = _store()
        listing = _listing(store)
        store.rate(listing.listing_id, "u2", 4)
        store.rate(listing.listing_id, "u3", 2)
        self.assertEqual(listing.average_rating, 3.0)

    def test_user_can_update_rating(self):
        store = _store()
        listing = _listing(store)
        store.rate(listing.listing_id, "u2", 5)
        store.rate(listing.listing_id, "u2", 1)
        self.assertEqual(listing.rating_count, 1)
        self.assertEqual(listing.average_rating, 1.0)

    def test_owner_cannot_rate_own(self):
        store = _store()
        listing = _listing(store)
        with self.assertRaises((ValueError, PermissionError)):
            store.rate(listing.listing_id, "u1", 5)

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
        self.store.rate(self.l1.listing_id, "u3", 5)
        results = self.store.search(sort_by="rating")
        self.assertEqual(results["items"][0]["listing_id"], self.l1.listing_id)

    def test_pagination(self):
        results = self.store.search(limit=2, offset=0)
        self.assertEqual(len(results["items"]), 2)
        results2 = self.store.search(limit=2, offset=2)
        self.assertLessEqual(len(results2["items"]), 1)

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

    def test_get_stats(self):
        stats = self.store.get_stats()
        self.assertEqual(stats["total_listings"], 3)
        self.assertIn("categories", stats)

    def test_to_dict_has_expected_fields(self):
        d = self.l1.to_dict()
        for key in ("listing_id", "name", "owner_username", "tags", "download_count", "average_rating"):
            self.assertIn(key, d)


if __name__ == "__main__":
    unittest.main(verbosity=2)
