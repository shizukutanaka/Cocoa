"""Tests for main/user_notifications.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from user_notifications import NotificationQueue, get_notification_queue


class TestNotificationQueue(unittest.TestCase):
    def setUp(self):
        self.q = NotificationQueue()

    def test_push_returns_notification(self):
        n = self.q.push("u1", "new_follower", "New Follower", "Someone followed you")
        self.assertIsNotNone(n.notification_id)
        self.assertEqual(n.user_id, "u1")
        self.assertEqual(n.kind, "new_follower")
        self.assertFalse(n.is_read)

    def test_get_notifications_empty(self):
        result = self.q.get_notifications("u1")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["unread_count"], 0)
        self.assertEqual(result["items"], [])

    def test_get_notifications_after_push(self):
        self.q.push("u1", "new_download", "Download", "Avatar downloaded")
        result = self.q.get_notifications("u1")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["unread_count"], 1)

    def test_notifications_newest_first(self):
        for i in range(3):
            self.q.push("u1", "system", f"Title {i}", f"Body {i}")
        items = self.q.get_notifications("u1")["items"]
        ids = [item["notification_id"] for item in items]
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_mark_read(self):
        n = self.q.push("u1", "new_review", "Review", "New review")
        ok = self.q.mark_read("u1", n.notification_id)
        self.assertTrue(ok)
        result = self.q.get_notifications("u1")
        self.assertEqual(result["unread_count"], 0)

    def test_mark_read_wrong_id_returns_false(self):
        ok = self.q.mark_read("u1", "nonexistent")
        self.assertFalse(ok)

    def test_mark_all_read(self):
        for _ in range(5):
            self.q.push("u1", "system", "T", "B")
        count = self.q.mark_all_read("u1")
        self.assertEqual(count, 5)
        result = self.q.get_notifications("u1")
        self.assertEqual(result["unread_count"], 0)

    def test_delete_notification(self):
        n = self.q.push("u1", "system", "T", "B")
        ok = self.q.delete_notification("u1", n.notification_id)
        self.assertTrue(ok)
        result = self.q.get_notifications("u1")
        self.assertEqual(result["total"], 0)

    def test_delete_nonexistent_returns_false(self):
        ok = self.q.delete_notification("u1", "no-such-id")
        self.assertFalse(ok)

    def test_unread_count(self):
        self.q.push("u1", "system", "T1", "B")
        self.q.push("u1", "system", "T2", "B")
        n = self.q.push("u1", "system", "T3", "B")
        self.q.mark_read("u1", n.notification_id)
        self.assertEqual(self.q.unread_count("u1"), 2)

    def test_unread_only_filter(self):
        n = self.q.push("u1", "system", "T1", "B")
        self.q.push("u1", "system", "T2", "B")
        self.q.mark_read("u1", n.notification_id)
        result = self.q.get_notifications("u1", unread_only=True)
        self.assertEqual(result["total"], 1)

    def test_pagination(self):
        for i in range(10):
            self.q.push("u1", "system", f"T{i}", "B")
        p1 = self.q.get_notifications("u1", limit=5, offset=0)
        p2 = self.q.get_notifications("u1", limit=5, offset=5)
        self.assertEqual(len(p1["items"]), 5)
        self.assertEqual(len(p2["items"]), 5)
        self.assertEqual(p1["total"], 10)

    def test_pagination_has_more_true(self):
        for i in range(10):
            self.q.push("u1", "system", f"T{i}", "B")
        result = self.q.get_notifications("u1", limit=5, offset=0)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 5)

    def test_pagination_has_more_false_last_page(self):
        for i in range(10):
            self.q.push("u1", "system", f"T{i}", "B")
        result = self.q.get_notifications("u1", limit=5, offset=5)
        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])

    def test_pagination_fields_present(self):
        self.q.push("u1", "system", "T", "B")
        result = self.q.get_notifications("u1", limit=10, offset=0)
        for key in ("total", "offset", "limit", "has_more", "next_offset", "unread_count", "items"):
            self.assertIn(key, result)

    def test_max_queue_size_enforced(self):
        q = NotificationQueue(max_per_user=5)
        for i in range(8):
            q.push("u1", "system", f"T{i}", "B")
        result = q.get_notifications("u1")
        self.assertLessEqual(result["total"], 5)

    def test_multiple_users_independent(self):
        self.q.push("u1", "system", "For U1", "B")
        self.q.push("u2", "system", "For U2", "B")
        u1 = self.q.get_notifications("u1")
        u2 = self.q.get_notifications("u2")
        self.assertEqual(u1["total"], 1)
        self.assertEqual(u2["total"], 1)

    def test_payload_stored(self):
        n = self.q.push("u1", "new_follower", "T", "B", {"follower_id": "u99"})
        d = n.to_dict()
        self.assertEqual(d["payload"]["follower_id"], "u99")

    def test_stats(self):
        self.q.push("u1", "system", "T", "B")
        self.q.push("u2", "system", "T", "B")
        s = self.q.stats()
        self.assertEqual(s["users_with_notifications"], 2)
        self.assertEqual(s["total_notifications"], 2)
        self.assertEqual(s["total_unread"], 2)

    def test_singleton(self):
        q1 = get_notification_queue()
        q2 = get_notification_queue()
        self.assertIs(q1, q2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
