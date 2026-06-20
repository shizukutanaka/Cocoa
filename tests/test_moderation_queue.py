"""Tests for main/moderation_queue.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from moderation_queue import (
    VALID_KINDS,
    ModerationItem,
    ModerationQueue,
    get_moderation_queue,
)


def _q() -> ModerationQueue:
    return ModerationQueue()


class TestModerationItem(unittest.TestCase):
    def test_to_dict(self):
        item = ModerationItem(
            item_id="mid1", kind="listing_report", source_id="rep1",
            subject_id="lst1", reporter_id="u1", reason="spam",
        )
        d = item.to_dict()
        self.assertEqual(d["item_id"], "mid1")
        self.assertEqual(d["status"], "pending")
        self.assertIsNone(d["resolved_at"])


class TestModerationQueue(unittest.TestCase):
    def setUp(self):
        self.q = _q()

    def test_enqueue_creates_item(self):
        item = self.q.enqueue("listing_report", "rep1", "lst1", "u1", "spam")
        self.assertEqual(item.kind, "listing_report")
        self.assertEqual(item.status, "pending")

    def test_enqueue_idempotent_by_source_id(self):
        item1 = self.q.enqueue("listing_report", "rep1", "lst1", "u1", "spam")
        item2 = self.q.enqueue("listing_report", "rep1", "lst2", "u2", "different")
        self.assertEqual(item1.item_id, item2.item_id)

    def test_enqueue_after_resolve_creates_new_item(self):
        # A new report for a source whose prior report was RESOLVED must create a
        # fresh open item (re-posted/re-offending content can be flagged again),
        # not silently return the closed one.
        item1 = self.q.enqueue("listing_report", "rep1", "lst1", "u1", "spam")
        self.q.update_status(item1.item_id, "resolved")
        item2 = self.q.enqueue("listing_report", "rep1", "lst1", "u2", "spam again")
        self.assertNotEqual(item1.item_id, item2.item_id)
        self.assertEqual(item2.status, "pending")
        # The source index now points at the fresh item.
        self.assertEqual(self.q.get(item2.item_id).source_id, "rep1")

    def test_enqueue_after_dismiss_creates_new_item(self):
        item1 = self.q.enqueue("listing_report", "rep2", "lst9", "u1", "noise")
        self.q.update_status(item1.item_id, "dismissed")
        item2 = self.q.enqueue("listing_report", "rep2", "lst9", "u3", "back again")
        self.assertNotEqual(item1.item_id, item2.item_id)
        self.assertEqual(item2.status, "pending")

    def test_enqueue_dedup_while_in_review(self):
        # An in-review (still open) item must still dedup.
        item1 = self.q.enqueue("listing_report", "rep3", "lst3", "u1", "spam")
        self.q.assign(item1.item_id, "admin1")  # → in_review
        item2 = self.q.enqueue("listing_report", "rep3", "lst3", "u2", "dup")
        self.assertEqual(item1.item_id, item2.item_id)

    def test_enqueue_invalid_kind_raises(self):
        with self.assertRaises(ValueError):
            self.q.enqueue("bad_kind", "s1", "sub1", "u1", "reason")

    def test_enqueue_invalid_priority_raises(self):
        with self.assertRaises(ValueError):
            self.q.enqueue("listing_report", "s1", "sub1", "u1", "reason", priority="critical")

    def test_get_item(self):
        item = self.q.enqueue("listing_report", "rep1", "lst1", "u1", "spam")
        fetched = self.q.get(item.item_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.item_id, item.item_id)

    def test_get_unknown_returns_none(self):
        self.assertIsNone(self.q.get("no-id"))

    def test_assign_sets_in_review(self):
        item = self.q.enqueue("listing_report", "rep1", "lst1", "u1", "spam")
        self.q.assign(item.item_id, "admin1")
        self.assertEqual(item.status, "in_review")
        self.assertEqual(item.assigned_to, "admin1")

    def test_assign_unknown_raises(self):
        with self.assertRaises(ValueError):
            self.q.assign("no-id", "admin1")

    def test_update_status_resolved(self):
        item = self.q.enqueue("listing_report", "rep1", "lst1", "u1", "spam")
        self.q.update_status(item.item_id, "resolved", "removed listing")
        self.assertEqual(item.status, "resolved")
        self.assertIsNotNone(item.resolved_at)
        self.assertEqual(item.notes, "removed listing")

    def test_update_status_dismissed(self):
        item = self.q.enqueue("listing_report", "rep1", "lst1", "u1", "spam")
        self.q.update_status(item.item_id, "dismissed")
        self.assertEqual(item.status, "dismissed")
        self.assertIsNotNone(item.resolved_at)

    def test_reopen_via_update_status_clears_resolved_at(self):
        # Closing then reopening must clear resolved_at so a pending/in_review
        # item never carries a stale resolution timestamp.
        item = self.q.enqueue("listing_report", "rep1", "lst1", "u1", "spam")
        self.q.update_status(item.item_id, "resolved")
        self.assertIsNotNone(item.resolved_at)
        self.q.update_status(item.item_id, "pending")
        self.assertEqual(item.status, "pending")
        self.assertIsNone(item.resolved_at)

    def test_assign_after_resolve_clears_resolved_at(self):
        item = self.q.enqueue("listing_report", "rep1", "lst1", "u1", "spam")
        self.q.update_status(item.item_id, "dismissed")
        self.assertIsNotNone(item.resolved_at)
        self.q.assign(item.item_id, "admin1")
        self.assertEqual(item.status, "in_review")
        self.assertIsNone(item.resolved_at)

    def test_update_status_invalid_raises(self):
        item = self.q.enqueue("listing_report", "rep1", "lst1", "u1", "spam")
        with self.assertRaises(ValueError):
            self.q.update_status(item.item_id, "archived")

    def test_update_status_unknown_raises(self):
        with self.assertRaises(ValueError):
            self.q.update_status("no-id", "resolved")

    def test_list_items_all(self):
        self.q.enqueue("listing_report", "r1", "l1", "u1", "spam")
        self.q.enqueue("review_report", "r2", "rev1", "u2", "abuse")
        result = self.q.list_items()
        self.assertEqual(result["total"], 2)

    def test_list_items_filter_by_status(self):
        item = self.q.enqueue("listing_report", "r1", "l1", "u1", "spam")
        self.q.enqueue("review_report", "r2", "rev1", "u2", "abuse")
        self.q.update_status(item.item_id, "resolved")
        result = self.q.list_items(status="pending")
        self.assertEqual(result["total"], 1)

    def test_list_items_filter_by_kind(self):
        self.q.enqueue("listing_report", "r1", "l1", "u1", "spam")
        self.q.enqueue("review_report", "r2", "rev1", "u2", "abuse")
        result = self.q.list_items(kind="review_report")
        self.assertEqual(result["total"], 1)

    def test_list_items_filter_by_priority(self):
        self.q.enqueue("listing_report", "r1", "l1", "u1", "spam", priority="high")
        self.q.enqueue("review_report", "r2", "rev1", "u2", "abuse", priority="low")
        result = self.q.list_items(priority="high")
        self.assertEqual(result["total"], 1)

    def test_list_items_filter_by_assigned_to(self):
        item = self.q.enqueue("listing_report", "r1", "l1", "u1", "spam")
        self.q.enqueue("review_report", "r2", "rev1", "u2", "abuse")
        self.q.assign(item.item_id, "admin1")
        result = self.q.list_items(assigned_to="admin1")
        self.assertEqual(result["total"], 1)

    def test_list_items_sort_by_priority(self):
        self.q.enqueue("listing_report", "r1", "l1", "u1", "x", priority="low")
        self.q.enqueue("review_report", "r2", "rev1", "u2", "x", priority="high")
        result = self.q.list_items(sort_by="priority")
        self.assertEqual(result["items"][0]["priority"], "high")

    def test_list_items_pagination(self):
        for i in range(5):
            self.q.enqueue("listing_report", f"r{i}", f"l{i}", "u1", "spam")
        result = self.q.list_items(limit=3, offset=0)
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["items"]), 3)
        self.assertTrue(result["has_more"])

    def test_get_stats(self):
        self.q.enqueue("listing_report", "r1", "l1", "u1", "spam", priority="high")
        self.q.enqueue("review_report", "r2", "rev1", "u2", "abuse", priority="medium")
        stats = self.q.get_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["pending"], 2)
        self.assertEqual(stats["open"], 2)
        self.assertIn("listing_report", stats["by_kind"])

    def test_get_stats_after_resolve(self):
        item = self.q.enqueue("listing_report", "r1", "l1", "u1", "spam")
        self.q.update_status(item.item_id, "resolved")
        stats = self.q.get_stats()
        self.assertEqual(stats["resolved"], 1)
        self.assertEqual(stats["open"], 0)

    def test_set_priority(self):
        item = self.q.enqueue("listing_report", "r1", "l1", "u1", "spam")
        self.q.set_priority(item.item_id, "high")
        self.assertEqual(item.priority, "high")

    def test_set_priority_invalid_raises(self):
        item = self.q.enqueue("listing_report", "r1", "l1", "u1", "spam")
        with self.assertRaises(ValueError):
            self.q.set_priority(item.item_id, "critical")

    def test_all_valid_kinds_work(self):
        for i, kind in enumerate(VALID_KINDS):
            item = self.q.enqueue(kind, f"src{i}", "sub1", "u1", "test")
            self.assertEqual(item.kind, kind)

    def test_list_items_serialized_status_matches_filter(self):
        """Filtering and to_dict() must happen under the same lock; verify that
        every serialized item's status is consistent with the filter applied."""
        item = self.q.enqueue("listing_report", "r1", "l1", "u1", "spam")
        self.q.update_status(item.item_id, "resolved")
        result = self.q.list_items(status="pending")
        for entry in result["items"]:
            self.assertEqual(entry["status"], "pending")

    def test_stats_open_count_consistent_with_pending_in_review(self):
        """get_stats() must compute all counts inside the lock so 'open' equals
        pending + in_review — a race between read and aggregation would corrupt this."""
        i1 = self.q.enqueue("listing_report", "r1", "l1", "u1", "spam", priority="high")
        i2 = self.q.enqueue("review_report", "r2", "rev1", "u2", "abuse")
        self.q.assign(i2.item_id, "admin1")
        stats = self.q.get_stats()
        self.assertEqual(stats["open"], stats["pending"] + stats["in_review"])
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["in_review"], 1)


class TestModerationQueuePaginationClamp(unittest.TestCase):
    def setUp(self):
        self.q = _q()
        for i in range(5):
            self.q.enqueue("listing_report", f"src{i}", "sub", "u1", "spam")

    def test_negative_offset_clamped(self):
        r = self.q.list_items(offset=-3, limit=2)
        self.assertEqual(r["offset"], 0)

    def test_zero_limit_clamped(self):
        r = self.q.list_items(offset=0, limit=0)
        self.assertGreaterEqual(r["limit"], 1)
        self.assertNotEqual(r["items"], [])

    def test_huge_limit_capped(self):
        r = self.q.list_items(offset=0, limit=10**9)
        self.assertLessEqual(r["limit"], 100)


class TestModerationQueueSingleton(unittest.TestCase):
    def test_singleton(self):
        a = get_moderation_queue()
        b = get_moderation_queue()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
