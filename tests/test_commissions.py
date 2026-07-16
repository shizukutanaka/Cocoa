"""Tests for main/commissions.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from commissions import CommissionRequest, CommissionStore, get_commission_store


def _create(store: CommissionStore, requester_id="u1", creator_id="creator1",
            title="Custom Avatar", description="I want a custom avatar") -> CommissionRequest:
    return store.create(
        requester_id=requester_id,
        requester_username="alice",
        creator_id=creator_id,
        title=title,
        description=description,
    )


class TestCommissionCreate(unittest.TestCase):
    def setUp(self):
        self.store = CommissionStore()

    def test_create_returns_commission(self):
        req = _create(self.store)
        self.assertEqual(req.status, "pending")
        self.assertEqual(req.requester_id, "u1")
        self.assertEqual(req.creator_id, "creator1")

    def test_create_sets_title(self):
        req = _create(self.store, title="My Request")
        self.assertEqual(req.title, "My Request")

    def test_self_request_raises(self):
        with self.assertRaises(ValueError):
            _create(self.store, requester_id="u1", creator_id="u1")

    def test_empty_title_raises(self):
        with self.assertRaises(ValueError):
            self.store.create("u1", "alice", "creator1", "   ", "description")

    def test_empty_description_raises(self):
        with self.assertRaises(ValueError):
            self.store.create("u1", "alice", "creator1", "Title", "   ")

    def test_negative_budget_raises(self):
        with self.assertRaises(ValueError):
            self.store.create("u1", "alice", "creator1", "Title", "desc", budget_credits=-1)

    def test_budget_zero_is_valid(self):
        req = self.store.create("u1", "alice", "creator1", "Title", "desc", budget_credits=0)
        self.assertEqual(req.budget_credits, 0)

    def test_budget_stored(self):
        req = self.store.create("u1", "alice", "creator1", "Title", "desc", budget_credits=500)
        self.assertEqual(req.budget_credits, 500)

    def test_request_id_unique(self):
        r1 = _create(self.store, requester_id="u1")
        r2 = _create(self.store, requester_id="u2", creator_id="creator2")
        self.assertNotEqual(r1.request_id, r2.request_id)


class TestCommissionRespond(unittest.TestCase):
    def setUp(self):
        self.store = CommissionStore()
        self.req = _create(self.store)

    def test_accept_changes_status(self):
        result = self.store.respond("creator1", self.req.request_id, accept=True, note="Sure!")
        self.assertEqual(result.status, "accepted")
        self.assertEqual(result.creator_note, "Sure!")

    def test_decline_changes_status(self):
        result = self.store.respond("creator1", self.req.request_id, accept=False, note="Busy")
        self.assertEqual(result.status, "declined")

    def test_non_creator_respond_raises(self):
        with self.assertRaises(PermissionError):
            self.store.respond("other_user", self.req.request_id, accept=True)

    def test_respond_unknown_raises(self):
        with self.assertRaises(ValueError):
            self.store.respond("creator1", "no-such-id", accept=True)

    def test_respond_already_accepted_raises(self):
        self.store.respond("creator1", self.req.request_id, accept=True)
        with self.assertRaises(ValueError):
            self.store.respond("creator1", self.req.request_id, accept=False)

    def test_respond_declined_raises(self):
        self.store.respond("creator1", self.req.request_id, accept=False)
        with self.assertRaises(ValueError):
            self.store.respond("creator1", self.req.request_id, accept=True)


class TestCommissionDeliver(unittest.TestCase):
    def setUp(self):
        self.store = CommissionStore()
        self.req = _create(self.store)
        self.store.respond("creator1", self.req.request_id, accept=True)

    def test_deliver_changes_status(self):
        result = self.store.deliver("creator1", self.req.request_id, "Here it is!")
        self.assertEqual(result.status, "delivered")
        self.assertEqual(result.delivery_note, "Here it is!")

    def test_deliver_with_listing_id(self):
        result = self.store.deliver("creator1", self.req.request_id, "Done", "listing123")
        self.assertEqual(result.delivery_listing_id, "listing123")

    def test_deliver_empty_note_raises(self):
        with self.assertRaises(ValueError):
            self.store.deliver("creator1", self.req.request_id, "   ")

    def test_deliver_non_creator_raises(self):
        with self.assertRaises(PermissionError):
            self.store.deliver("other_user", self.req.request_id, "Done")

    def test_deliver_pending_commission_raises(self):
        req2 = _create(self.store, requester_id="u2", creator_id="creator2")
        with self.assertRaises(ValueError):
            self.store.deliver("creator2", req2.request_id, "Done")

    def test_deliver_unknown_raises(self):
        with self.assertRaises(ValueError):
            self.store.deliver("creator1", "no-such-id", "Done")


class TestCommissionClose(unittest.TestCase):
    def setUp(self):
        self.store = CommissionStore()
        self.req = _create(self.store)

    def test_close_pending_commission(self):
        result = self.store.close("u1", self.req.request_id)
        self.assertEqual(result.status, "closed")

    def test_close_after_delivery(self):
        self.store.respond("creator1", self.req.request_id, accept=True)
        self.store.deliver("creator1", self.req.request_id, "Delivered!")
        result = self.store.close("u1", self.req.request_id)
        self.assertEqual(result.status, "closed")

    def test_close_non_requester_raises(self):
        with self.assertRaises(PermissionError):
            self.store.close("creator1", self.req.request_id)

    def test_close_declined_raises(self):
        self.store.respond("creator1", self.req.request_id, accept=False)
        with self.assertRaises(ValueError):
            self.store.close("u1", self.req.request_id)

    def test_close_already_closed_raises(self):
        self.store.close("u1", self.req.request_id)
        with self.assertRaises(ValueError):
            self.store.close("u1", self.req.request_id)

    def test_close_unknown_raises(self):
        with self.assertRaises(ValueError):
            self.store.close("u1", "no-such-id")


class TestCommissionList(unittest.TestCase):
    def setUp(self):
        self.store = CommissionStore()
        _create(self.store, requester_id="u1", creator_id="creator1")
        _create(self.store, requester_id="u1", creator_id="creator2")
        _create(self.store, requester_id="u2", creator_id="creator1")

    def test_list_received_by_creator(self):
        result = self.store.list_received("creator1")
        self.assertEqual(result["total"], 2)

    def test_list_sent_by_requester(self):
        result = self.store.list_sent("u1")
        self.assertEqual(result["total"], 2)

    def test_list_received_filter_by_status(self):
        reqs = self.store.list_received("creator1")["items"]
        self.store.respond("creator1", reqs[0]["request_id"], accept=True)
        accepted = self.store.list_received("creator1", status="accepted")
        self.assertEqual(accepted["total"], 1)

    def test_list_received_filter_status_matches_serialized_status(self):
        """Items in a status-filtered result must carry that status in to_dict()."""
        reqs = self.store.list_received("creator1")["items"]
        self.store.respond("creator1", reqs[0]["request_id"], accept=True)
        accepted = self.store.list_received("creator1", status="accepted")
        for item in accepted["items"]:
            self.assertEqual(item["status"], "accepted")

    def test_list_pagination(self):
        page1 = self.store.list_sent("u1", limit=1, offset=0)
        page2 = self.store.list_sent("u1", limit=1, offset=1)
        self.assertEqual(page1["total"], 2)
        self.assertTrue(page1["has_more"])
        self.assertFalse(page2["has_more"])

    def test_list_empty_for_unknown_user(self):
        result = self.store.list_sent("nobody")
        self.assertEqual(result["total"], 0)

    def test_pagination_keys_present(self):
        result = self.store.list_received("creator1")
        for key in ("total", "offset", "limit", "has_more", "next_offset", "items"):
            self.assertIn(key, result)


class TestCommissionGet(unittest.TestCase):
    def setUp(self):
        self.store = CommissionStore()
        self.req = _create(self.store)

    def test_get_returns_commission(self):
        result = self.store.get(self.req.request_id)
        self.assertIsNotNone(result)
        self.assertEqual(result.request_id, self.req.request_id)

    def test_get_unknown_returns_none(self):
        result = self.store.get("no-such-id")
        self.assertIsNone(result)


class TestCommissionToDict(unittest.TestCase):
    def setUp(self):
        self.store = CommissionStore()
        self.req = _create(self.store)

    def test_to_dict_has_required_keys(self):
        d = self.req.to_dict()
        for key in ("request_id", "requester_id", "creator_id", "title",
                    "description", "budget_credits", "status", "created_at"):
            self.assertIn(key, d)

    def test_to_dict_status_pending(self):
        d = self.req.to_dict()
        self.assertEqual(d["status"], "pending")


class TestCommissionQuota(unittest.TestCase):
    def test_quota_blocks_at_limit(self):
        store = CommissionStore()
        from commissions import _MAX_COMMISSIONS_PER_USER
        for i in range(_MAX_COMMISSIONS_PER_USER):
            store.create("u1", "alice", f"creator{i}", "Title", "desc")
        with self.assertRaises(ValueError):
            store.create("u1", "alice", "creator_extra", "Title", "desc")

    def test_quota_counts_accepted_commissions(self):
        """Accepted commissions are still open — they must count against the cap.
        A user should not bypass the limit by having all their commissions accepted."""
        store = CommissionStore()
        from commissions import _MAX_COMMISSIONS_PER_USER
        # Create one pending commission and accept it, leaving the pending bucket empty
        req = store.create("u1", "alice", "creator0", "Title", "desc")
        store.respond("creator0", req.request_id, accept=True)
        # Fill up to the limit with more pending ones (total open = accepted + pending)
        for i in range(1, _MAX_COMMISSIONS_PER_USER):
            store.create("u1", "alice", f"creator{i}", "Title", "desc")
        # Now open count = 1 accepted + 99 pending = 100 = limit → should raise
        with self.assertRaises(ValueError):
            store.create("u1", "alice", "creator_extra", "Title", "desc")

    def test_quota_per_user_independent(self):
        store = CommissionStore()
        from commissions import _MAX_COMMISSIONS_PER_USER
        for i in range(_MAX_COMMISSIONS_PER_USER):
            store.create("u1", "alice", f"creator{i}", "Title", "desc")
        # A different requester is unaffected
        r = store.create("u2", "bob", "creator0", "Title", "desc")
        self.assertEqual(r.requester_id, "u2")


class TestCommissionSingleton(unittest.TestCase):
    def test_singleton(self):
        a = get_commission_store()
        b = get_commission_store()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
