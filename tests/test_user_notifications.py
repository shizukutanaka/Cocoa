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

    def test_delete_all_for_user_removes_notifications(self):
        self.q.push("u1", "system", "T1", "B")
        self.q.push("u1", "system", "T2", "B")
        removed = self.q.delete_all_for_user("u1")
        self.assertEqual(removed, 2)
        result = self.q.get_notifications("u1")
        self.assertEqual(result["total"], 0)

    def test_delete_all_for_user_clears_muted_kinds(self):
        self.q.mute_kind("u1", "system")
        self.q.delete_all_for_user("u1")
        self.assertEqual(self.q.get_muted_kinds("u1"), [])

    def test_delete_all_for_user_does_not_touch_other_users(self):
        self.q.push("u1", "system", "T", "B")
        self.q.push("u2", "system", "T", "B")
        self.q.delete_all_for_user("u1")
        result = self.q.get_notifications("u2")
        self.assertEqual(result["total"], 1)

    def test_delete_all_for_unknown_user_returns_zero(self):
        self.assertEqual(self.q.delete_all_for_user("no-such-user"), 0)

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

    def test_unread_only_items_serialized_as_unread(self):
        """Every item returned by unread_only=True must have is_read=False in to_dict()."""
        n = self.q.push("u1", "system", "T1", "B")
        self.q.push("u1", "system", "T2", "B")
        self.q.mark_read("u1", n.notification_id)
        result = self.q.get_notifications("u1", unread_only=True)
        for item in result["items"]:
            self.assertFalse(item["is_read"])
        self.assertEqual(result["unread_count"], 1)

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


class TestNotificationPreferences(unittest.TestCase):
    def setUp(self):
        self.q = NotificationQueue()

    def test_no_muted_kinds_by_default(self):
        self.assertEqual(self.q.get_muted_kinds("u1"), [])

    def test_mute_kind_silences_push(self):
        self.q.mute_kind("u1", "new_follower")
        result = self.q.push("u1", "new_follower", "T", "B")
        self.assertIsNone(result)

    def test_muted_kind_not_stored(self):
        self.q.mute_kind("u1", "new_follower")
        self.q.push("u1", "new_follower", "T", "B")
        notifs = self.q.get_notifications("u1")
        self.assertEqual(notifs["total"], 0)

    def test_unmuted_kind_is_delivered(self):
        self.q.mute_kind("u1", "new_follower")
        result = self.q.push("u1", "system", "T", "B")
        self.assertIsNotNone(result)

    def test_unmute_kind_restores_delivery(self):
        self.q.mute_kind("u1", "new_follower")
        self.q.unmute_kind("u1", "new_follower")
        result = self.q.push("u1", "new_follower", "T", "B")
        self.assertIsNotNone(result)

    def test_get_muted_kinds_returns_sorted_list(self):
        self.q.mute_kind("u1", "system")
        self.q.mute_kind("u1", "new_follower")
        kinds = self.q.get_muted_kinds("u1")
        self.assertEqual(kinds, sorted(kinds))

    def test_set_muted_kinds_replaces_set(self):
        self.q.mute_kind("u1", "old_kind")
        self.q.set_muted_kinds("u1", ["new_download", "new_review"])
        self.assertNotIn("old_kind", self.q.get_muted_kinds("u1"))
        self.assertIn("new_download", self.q.get_muted_kinds("u1"))

    def test_set_muted_kinds_empty_clears_all(self):
        self.q.mute_kind("u1", "system")
        self.q.set_muted_kinds("u1", [])
        self.assertEqual(self.q.get_muted_kinds("u1"), [])

    def test_mute_does_not_affect_other_users(self):
        self.q.mute_kind("u1", "system")
        result = self.q.push("u2", "system", "T", "B")
        self.assertIsNotNone(result)

    def test_set_muted_kinds_filters_unknown_kinds(self):
        # An adversarially large list of unknown kinds must not be stored —
        # only known notification kinds are accepted (DoS prevention).
        garbage = [f"fake_kind_{i}" for i in range(10_000)]
        self.q.set_muted_kinds("u1", garbage)
        self.assertEqual(self.q.get_muted_kinds("u1"), [])

    def test_set_muted_kinds_accepts_valid_kinds(self):
        self.q.set_muted_kinds("u1", ["new_follower", "new_download"])
        kinds = self.q.get_muted_kinds("u1")
        self.assertIn("new_follower", kinds)
        self.assertIn("new_download", kinds)

    def test_set_muted_kinds_accepts_direct_push_kinds(self):
        # Kinds pushed directly (not via a template) must be mutable too —
        # these are the ones users most want to control.
        direct = ["price_drop", "tip_received", "commission_received",
                  "commission_response", "commission_delivered", "commission_closed",
                  "commission_disputed",
                  "refund_approved", "refund_rejected", "dispute_resolved",
                  "referral_bonus",
                  "saved_search_match", "system"]
        self.q.set_muted_kinds("u1", direct)
        muted = self.q.get_muted_kinds("u1")
        for kind in direct:
            self.assertIn(kind, muted)

    def test_muting_price_drop_via_set_actually_suppresses(self):
        # End-to-end: set_muted_kinds(["price_drop"]) must cause a price_drop
        # push to be dropped (regression: it was filtered out as "unknown").
        self.q.set_muted_kinds("u1", ["price_drop"])
        result = self.q.push("u1", "price_drop", "T", "B")
        self.assertIsNone(result)

    def test_muting_tip_via_set_actually_suppresses(self):
        self.q.set_muted_kinds("u1", ["tip_received"])
        self.assertIsNone(self.q.push("u1", "tip_received", "T", "B"))

    def test_commission_closed_is_pushable(self):
        result = self.q.push("creator1", "commission_closed", "クローズ", "依頼がクローズされました")
        self.assertIsNotNone(result)
        self.assertEqual(result.kind, "commission_closed")

    def test_muting_commission_closed_suppresses(self):
        self.q.set_muted_kinds("creator1", ["commission_closed"])
        result = self.q.push("creator1", "commission_closed", "クローズ", "依頼がクローズされました")
        self.assertIsNone(result)

    def test_refund_approved_is_pushable(self):
        result = self.q.push("u1", "refund_approved", "払い戻し承認", "100 クレジットが返還されました")
        self.assertIsNotNone(result)
        self.assertEqual(result.kind, "refund_approved")

    def test_refund_rejected_is_pushable(self):
        result = self.q.push("u1", "refund_rejected", "払い戻し却下", "却下されました")
        self.assertIsNotNone(result)
        self.assertEqual(result.kind, "refund_rejected")

    def test_muting_refund_approved_suppresses(self):
        self.q.set_muted_kinds("u1", ["refund_approved"])
        self.assertIsNone(self.q.push("u1", "refund_approved", "T", "B"))

    def test_muting_refund_rejected_suppresses(self):
        self.q.set_muted_kinds("u1", ["refund_rejected"])
        self.assertIsNone(self.q.push("u1", "refund_rejected", "T", "B"))

    def test_dispute_resolved_is_pushable(self):
        result = self.q.push("u1", "dispute_resolved", "争議解決", "返金されました")
        self.assertIsNotNone(result)
        self.assertEqual(result.kind, "dispute_resolved")

    def test_muting_dispute_resolved_suppresses(self):
        self.q.set_muted_kinds("u1", ["dispute_resolved"])
        self.assertIsNone(self.q.push("u1", "dispute_resolved", "T", "B"))

    def test_referral_bonus_is_pushable(self):
        result = self.q.push("referrer1", "referral_bonus", "ボーナス付与", "50 クレジット獲得")
        self.assertIsNotNone(result)
        self.assertEqual(result.kind, "referral_bonus")

    def test_muting_referral_bonus_suppresses(self):
        self.q.set_muted_kinds("referrer1", ["referral_bonus"])
        self.assertIsNone(self.q.push("referrer1", "referral_bonus", "T", "B"))


class TestNotificationTemplates(unittest.TestCase):
    def setUp(self):
        from user_notifications import NotificationQueue
        self.q = NotificationQueue()

    def test_push_from_template_new_follower(self):
        notif = self.q.push_from_template("u1", "new_follower", follower_username="alice")
        self.assertIsNotNone(notif)
        self.assertEqual(notif.kind, "new_follower")
        self.assertIn("alice", notif.body)

    def test_push_from_template_new_download(self):
        notif = self.q.push_from_template(
            "u1", "new_download", downloader_username="bob", listing_name="Cool Cat"
        )
        self.assertIsNotNone(notif)
        self.assertIn("bob", notif.body)
        self.assertIn("Cool Cat", notif.body)

    def test_push_from_template_new_review(self):
        notif = self.q.push_from_template(
            "u1", "new_review", reviewer_username="carol", listing_name="My Avatar", stars=5
        )
        self.assertIn("5", notif.body)
        self.assertIn("carol", notif.body)

    def test_push_from_template_credit_gifted(self):
        notif = self.q.push_from_template(
            "u1", "credit_gifted", sender_username="dave", amount=100
        )
        self.assertIn("100", notif.body)

    def test_push_from_template_unknown_raises(self):
        from user_notifications import NotificationQueue
        q = NotificationQueue()
        with self.assertRaises(ValueError):
            q.push_from_template("u1", "no_such_template", foo="bar")

    def test_push_from_template_respects_mute(self):
        self.q.mute_kind("u1", "new_follower")
        notif = self.q.push_from_template("u1", "new_follower", follower_username="eve")
        self.assertIsNone(notif)

    def test_push_from_template_payload_stored(self):
        notif = self.q.push_from_template(
            "u1", "new_follower",
            payload={"follower_id": "u2"},
            follower_username="frank",
        )
        self.assertEqual(notif.payload["follower_id"], "u2")


class TestPushBatch(unittest.TestCase):
    def setUp(self):
        from user_notifications import NotificationQueue
        self.q = NotificationQueue()

    def test_push_batch_delivers_to_all(self):
        count = self.q.push_batch(["u1", "u2", "u3"], "system", "Hello", "World")
        self.assertEqual(count, 3)

    def test_push_batch_skips_muted(self):
        self.q.mute_kind("u2", "system")
        count = self.q.push_batch(["u1", "u2", "u3"], "system", "Alert", "Message")
        self.assertEqual(count, 2)

    def test_push_batch_empty_list(self):
        count = self.q.push_batch([], "system", "Test", "Body")
        self.assertEqual(count, 0)

    def test_push_batch_each_user_gets_notification(self):
        self.q.push_batch(["u1", "u2"], "system_announcement", "News", "Big news")
        for uid in ("u1", "u2"):
            r = self.q.get_notifications(uid)
            self.assertEqual(r["total"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
