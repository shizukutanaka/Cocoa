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


if __name__ == "__main__":
    unittest.main(verbosity=2)
