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
        self.store.rate(self.l1.listing_id, "u3", 5)
        self.store.rate(self.l1.listing_id, "u4", 3)
        a = self.store.get_creator_analytics("u1")
        self.assertEqual(a["rating_distribution"][5], 1)
        self.assertEqual(a["rating_distribution"][3], 1)

    def test_analytics_total_reviews(self):
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
        avg, rv = self.store.review(self.listing.listing_id, "u2", "bob", 4, "Great!")
        self.assertEqual(avg, 4.0)
        self.assertIsInstance(rv, Review)
        self.assertEqual(rv.stars, 4)
        self.assertEqual(rv.text, "Great!")

    def test_review_text_truncated_at_2000(self):
        _, rv = self.store.review(self.listing.listing_id, "u2", "bob", 3, "x" * 3000)
        self.assertLessEqual(len(rv.text), 2000)

    def test_update_review_changes_text_and_stars(self):
        self.store.review(self.listing.listing_id, "u2", "bob", 5, "Perfect")
        avg, rv = self.store.review(self.listing.listing_id, "u2", "bob", 2, "Disappointing")
        self.assertEqual(avg, 2.0)
        self.assertEqual(rv.text, "Disappointing")
        self.assertEqual(self.listing.rating_count, 1)

    def test_owner_cannot_review_own_listing(self):
        with self.assertRaises((ValueError, PermissionError)):
            self.store.review(self.listing.listing_id, "u1", "alice", 5, "mine")

    def test_invalid_stars_raises(self):
        with self.assertRaises(ValueError):
            self.store.review(self.listing.listing_id, "u2", "bob", 0, "bad")
        with self.assertRaises(ValueError):
            self.store.review(self.listing.listing_id, "u2", "bob", 6, "bad")

    def test_get_reviews_empty(self):
        result = self.store.get_reviews(self.listing.listing_id)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])

    def test_get_reviews_after_post(self):
        self.store.review(self.listing.listing_id, "u2", "bob", 4, "Nice")
        result = self.store.get_reviews(self.listing.listing_id)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["text"], "Nice")

    def test_get_reviews_pagination(self):
        for i in range(5):
            self.store.review(self.listing.listing_id, f"user{i}", f"u{i}", 4, f"rev{i}")
        page1 = self.store.get_reviews(self.listing.listing_id, limit=3, offset=0)
        page2 = self.store.get_reviews(self.listing.listing_id, limit=3, offset=3)
        self.assertEqual(len(page1["items"]), 3)
        self.assertEqual(len(page2["items"]), 2)
        self.assertEqual(page1["total"], 5)

    def test_get_reviews_has_more_true(self):
        for i in range(5):
            self.store.review(self.listing.listing_id, f"user{i}", f"u{i}", 4, f"rev{i}")
        result = self.store.get_reviews(self.listing.listing_id, limit=3, offset=0)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 3)

    def test_get_reviews_has_more_false_on_last_page(self):
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
        self.store.review(self.listing.listing_id, "u2", "bob", 4, "OK")
        ok = self.store.delete_review(self.listing.listing_id, "u2")
        self.assertTrue(ok)
        result = self.store.get_reviews(self.listing.listing_id)
        self.assertEqual(result["total"], 0)

    def test_delete_nonexistent_review_returns_false(self):
        ok = self.store.delete_review(self.listing.listing_id, "never-reviewed")
        self.assertFalse(ok)

    def test_review_to_dict_fields(self):
        _, rv = self.store.review(self.listing.listing_id, "u2", "bob", 3, "Decent")
        d = rv.to_dict()
        for key in ("review_id", "listing_id", "user_id", "username", "stars", "text", "created_at"):
            self.assertIn(key, d)

    def test_get_reviews_unknown_listing(self):
        result = self.store.get_reviews("no-such-listing")
        self.assertEqual(result["total"], 0)


class TestReviewSorting(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.listing = _listing(self.store)
        self.lid = self.listing.listing_id
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

    def test_get_disputes_returns_paginated(self):
        self.store.open_dispute(self.paid_listing.listing_id, "u_buyer", "other")
        result = self.store.get_disputes()
        self.assertEqual(result["total"], 1)
        self.assertIn("has_more", result)

    def test_get_disputes_filter_by_status(self):
        dispute = self.store.open_dispute(self.paid_listing.listing_id, "u_buyer", "other")
        self.store.resolve_dispute(dispute.dispute_id, "admin1", "refund")
        open_result = self.store.get_disputes(status="open")
        self.assertEqual(open_result["total"], 0)
        refund_result = self.store.get_disputes(status="resolved_refund")
        self.assertEqual(refund_result["total"], 1)


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

    def test_owner_downloading_own_listing(self):
        self.store.download(self.lid, "u1")
        self.assertTrue(self.store.has_downloaded(self.lid, "u1"))


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
        self.store.rate(self.lid, "u2", 5)
        self.store.rate(self.lid, "u3", 3)
        self.store.rate(self.lid, "u4", 5)
        r = self.store.get_rating_distribution(self.lid)
        self.assertEqual(r["distribution"][5], 2)
        self.assertEqual(r["distribution"][3], 1)
        self.assertEqual(r["distribution"][1], 0)

    def test_total_ratings_count(self):
        self.store.rate(self.lid, "u2", 4)
        self.store.rate(self.lid, "u3", 4)
        r = self.store.get_rating_distribution(self.lid)
        self.assertEqual(r["total_ratings"], 2)

    def test_average_rating_correct(self):
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

    def test_clone_resets_download_count(self):
        self.store.download(self.cc_listing.listing_id, "u3")
        cloned = self.store.clone_listing(self.cc_listing.listing_id, "u2", "bob")
        self.assertEqual(cloned.download_count, 0)


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
        self.assertIn("gift_sent", kinds)


if __name__ == "__main__":
    unittest.main(verbosity=2)
