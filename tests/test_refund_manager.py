"""Tests for main/refund_manager.py"""
import sys
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from refund_manager import (
    REFUND_WINDOW_HOURS,
    RefundManager,
    RefundRequest,
    RefundStore,
    get_refund_manager,
)


class _FakeOrderItem:
    def __init__(self, owner_id, final_price, quantity=1, listing_id="lst1"):
        self.owner_id = owner_id
        self.final_price = final_price
        self.quantity = quantity
        self.listing_id = listing_id


class _FakeOrder:
    def __init__(self, order_id, user_id, total_credits, status="completed",
                 age_hours=0, items=None):
        self.order_id = order_id
        self.user_id = user_id
        self.total_credits = total_credits
        self.status = status
        self.created_at = datetime.now(timezone.utc) - timedelta(hours=age_hours)
        self.items = items or []


class _FakeCartStore:
    def __init__(self, orders=None):
        self._orders = {o.order_id: o for o in (orders or [])}

    def get_order(self, order_id):
        return self._orders.get(order_id)


class _FakeCartManager:
    def __init__(self, orders=None):
        self.store = _FakeCartStore(orders)


class _FakeMarketplace:
    def __init__(self, credits=None):
        self._lock = threading.Lock()
        self._credits = credits or {}
        self._ledger = []

    def _append_ledger(self, user_id, delta, kind, ref_id="", balance_after=0):
        self._ledger.append({"user_id": user_id, "delta": delta, "kind": kind,
                              "ref_id": ref_id, "balance_after": balance_after})

    def get_balance(self, user_id):
        return self._credits.get(user_id, 0)

    def record_platform_subsidy(self, amount, ref_id="", kind="platform_subsidy"):
        with self._lock:
            new_bal = self._credits.get("__platform__", 0) - amount
            self._credits["__platform__"] = new_bal
            self._append_ledger("__platform__", -amount, kind, ref_id=ref_id, balance_after=new_bal)
            return new_bal

    def credit(self, user_id, amount, kind, ref_id=""):
        if amount <= 0:
            raise ValueError("amount must be positive")
        with self._lock:
            new_bal = self._credits.get(user_id, 0) + amount
            self._credits[user_id] = new_bal
            self._append_ledger(user_id, amount, kind, ref_id=ref_id, balance_after=new_bal)
            return new_bal

    def debit(self, user_id, amount, kind, ref_id=""):
        if amount <= 0:
            raise ValueError("amount must be positive")
        with self._lock:
            balance = self._credits.get(user_id, 0)
            if balance < amount:
                raise ValueError(f"残高不足 (残高: {balance}, 必要: {amount})")
            new_bal = balance - amount
            self._credits[user_id] = new_bal
            self._append_ledger(user_id, -amount, kind, ref_id=ref_id, balance_after=new_bal)
            return new_bal


def _admin_payload(sub="admin1"):
    return {"sub": sub, "role": "admin"}


def _user_payload(sub="u1"):
    return {"sub": sub, "role": "user"}


class TestRefundRequest(unittest.TestCase):
    def test_to_dict_keys(self):
        req = RefundRequest(
            request_id="r1", order_id="o1", user_id="u1",
            total_credits=100, reason="changed mind",
        )
        d = req.to_dict()
        for key in ("request_id", "order_id", "user_id", "total_credits",
                    "reason", "status", "admin_notes", "resolved_by",
                    "created_at", "resolved_at"):
            self.assertIn(key, d)

    def test_default_status_pending(self):
        req = RefundRequest(
            request_id="r1", order_id="o1", user_id="u1",
            total_credits=50, reason="test",
        )
        self.assertEqual(req.status, "pending")


class TestRefundStore(unittest.TestCase):
    def setUp(self):
        self.store = RefundStore()

    def test_create_returns_request(self):
        req = self.store.create("o1", "u1", 100, "reason")
        self.assertEqual(req.order_id, "o1")
        self.assertEqual(req.user_id, "u1")
        self.assertEqual(req.total_credits, 100)
        self.assertEqual(req.status, "pending")

    def test_create_duplicate_pending_raises(self):
        self.store.create("o1", "u1", 100, "reason")
        with self.assertRaises(ValueError):
            self.store.create("o1", "u1", 100, "duplicate")

    def test_create_after_rejected_allowed(self):
        req = self.store.create("o1", "u1", 100, "reason")
        self.store.update(req.request_id, "rejected", "denied", "admin1")
        # rejected → can create again for same order
        req2 = self.store.create("o1", "u1", 100, "retry")
        self.assertNotEqual(req.request_id, req2.request_id)

    def test_get_existing(self):
        req = self.store.create("o1", "u1", 100, "reason")
        found = self.store.get(req.request_id)
        self.assertIsNotNone(found)
        self.assertEqual(found.request_id, req.request_id)

    def test_get_unknown_returns_none(self):
        self.assertIsNone(self.store.get("nope"))

    def test_get_by_order(self):
        req = self.store.create("o1", "u1", 100, "reason")
        found = self.store.get_by_order("o1")
        self.assertIsNotNone(found)
        self.assertEqual(found.request_id, req.request_id)

    def test_list_all(self):
        self.store.create("o1", "u1", 100, "r1")
        self.store.create("o2", "u2", 200, "r2")
        result = self.store.list_requests()
        self.assertEqual(result["total"], 2)

    def test_list_filter_status(self):
        req = self.store.create("o1", "u1", 100, "r1")
        self.store.create("o2", "u2", 200, "r2")
        self.store.update(req.request_id, "approved", "", "admin1")
        result = self.store.list_requests(status="pending")
        self.assertEqual(result["total"], 1)

    def test_list_filter_user(self):
        self.store.create("o1", "u1", 100, "r1")
        self.store.create("o2", "u2", 200, "r2")
        result = self.store.list_requests(user_id="u1")
        self.assertEqual(result["total"], 1)

    def test_update_sets_status_and_resolved_at(self):
        req = self.store.create("o1", "u1", 100, "reason")
        updated = self.store.update(req.request_id, "approved", "ok", "admin1")
        self.assertEqual(updated.status, "approved")
        self.assertIsNotNone(updated.resolved_at)
        self.assertEqual(updated.resolved_by, "admin1")

    def test_update_unknown_raises(self):
        with self.assertRaises(ValueError):
            self.store.update("nope", "approved", "", "admin1")

    def test_reason_truncated(self):
        req = self.store.create("o1", "u1", 100, "x" * 1500)
        self.assertEqual(len(req.reason), 1000)

    def test_pagination(self):
        for i in range(5):
            self.store.create(f"o{i}", "u1", 10 * (i + 1), "r")
        result = self.store.list_requests(limit=2, offset=0)
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["items"]), 2)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 2)


class TestRefundManagerRequest(unittest.TestCase):
    def _setup(self, age_hours=0, status="completed"):
        order = _FakeOrder("o1", "u1", 300, status=status, age_hours=age_hours)
        cart = _FakeCartManager([order])
        mgr = RefundManager()
        return mgr, cart

    def test_request_refund_success(self):
        mgr, cart = self._setup()
        result = mgr.request_refund("u1", "o1", "no longer needed", cart)
        self.assertEqual(result["order_id"], "o1")
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["total_credits"], 300)

    def test_request_refund_wrong_user_raises(self):
        mgr, cart = self._setup()
        with self.assertRaises(ValueError):
            mgr.request_refund("other_user", "o1", "reason", cart)

    def test_request_refund_unknown_order_raises(self):
        mgr, cart = self._setup()
        with self.assertRaises(ValueError):
            mgr.request_refund("u1", "unknown_order", "reason", cart)

    def test_request_refund_past_window_raises(self):
        mgr, cart = self._setup(age_hours=REFUND_WINDOW_HOURS + 1)
        with self.assertRaises(ValueError):
            mgr.request_refund("u1", "o1", "too late", cart)

    def test_request_refund_non_completed_order_raises(self):
        mgr, cart = self._setup(status="refunded")
        with self.assertRaises(ValueError):
            mgr.request_refund("u1", "o1", "already refunded", cart)

    def test_request_refund_empty_reason_raises(self):
        mgr, cart = self._setup()
        with self.assertRaises(ValueError):
            mgr.request_refund("u1", "o1", "  ", cart)

    def test_request_refund_duplicate_pending_raises(self):
        mgr, cart = self._setup()
        mgr.request_refund("u1", "o1", "reason", cart)
        with self.assertRaises(ValueError):
            mgr.request_refund("u1", "o1", "again", cart)


class TestRefundManagerAdmin(unittest.TestCase):
    def _setup(self):
        order = _FakeOrder("o1", "u1", 500)
        cart = _FakeCartManager([order])
        mkt = _FakeMarketplace(credits={"u1": 100})
        mgr = RefundManager()
        mgr.request_refund("u1", "o1", "want refund", cart)
        # get request_id
        result = mgr.store.list_requests()
        request_id = result["items"][0]["request_id"]
        return mgr, cart, mkt, request_id

    def test_approve_returns_credits(self):
        mgr, cart, mkt, rid = self._setup()
        result = mgr.approve_refund(_admin_payload(), rid, mkt, cart)
        self.assertEqual(result["credits_returned"], 500)
        self.assertEqual(mkt._credits["u1"], 600)  # 100 + 500

    def test_approve_records_ledger(self):
        mgr, cart, mkt, rid = self._setup()
        mgr.approve_refund(_admin_payload(), rid, mkt, cart)
        entry = next(e for e in mkt._ledger if e["kind"] == "refund")
        self.assertEqual(entry["delta"], 500)

    def test_approve_marks_order_refunded(self):
        mgr, cart, mkt, rid = self._setup()
        mgr.approve_refund(_admin_payload(), rid, mkt, cart)
        order = cart.store.get_order("o1")
        self.assertEqual(order.status, "refunded")

    def test_approve_non_admin_raises(self):
        mgr, cart, mkt, rid = self._setup()
        with self.assertRaises(PermissionError):
            mgr.approve_refund(_user_payload(), rid, mkt, cart)

    def test_approve_unknown_request_raises(self):
        mgr, cart, mkt, _ = self._setup()
        with self.assertRaises(ValueError):
            mgr.approve_refund(_admin_payload(), "nope", mkt, cart)

    def test_approve_already_approved_raises(self):
        mgr, cart, mkt, rid = self._setup()
        mgr.approve_refund(_admin_payload(), rid, mkt, cart)
        with self.assertRaises(ValueError):
            mgr.approve_refund(_admin_payload(), rid, mkt, cart)

    def test_reject_sets_status(self):
        mgr, cart, mkt, rid = self._setup()
        result = mgr.reject_refund(_admin_payload(), rid, notes="invalid claim")
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["admin_notes"], "invalid claim")

    def test_reject_non_admin_raises(self):
        mgr, cart, mkt, rid = self._setup()
        with self.assertRaises(PermissionError):
            mgr.reject_refund(_user_payload(), rid)

    def test_reject_unknown_raises(self):
        mgr = RefundManager()
        with self.assertRaises(ValueError):
            mgr.reject_refund(_admin_payload(), "nope")

    def test_reject_already_rejected_raises(self):
        mgr, cart, mkt, rid = self._setup()
        mgr.reject_refund(_admin_payload(), rid)
        with self.assertRaises(ValueError):
            mgr.reject_refund(_admin_payload(), rid)

    def test_list_refunds_admin(self):
        mgr, cart, mkt, rid = self._setup()
        result = mgr.list_refunds(_admin_payload())
        self.assertEqual(result["total"], 1)

    def test_list_refunds_non_admin_raises(self):
        mgr = RefundManager()
        with self.assertRaises(PermissionError):
            mgr.list_refunds(_user_payload())

    def test_list_refunds_filter_status(self):
        mgr, cart, mkt, rid = self._setup()
        mgr.approve_refund(_admin_payload(), rid, mkt, cart)
        result = mgr.list_refunds(_admin_payload(), status="approved")
        self.assertEqual(result["total"], 1)
        result2 = mgr.list_refunds(_admin_payload(), status="pending")
        self.assertEqual(result2["total"], 0)

    def test_list_refunds_invalid_status_raises(self):
        mgr = RefundManager()
        with self.assertRaises(ValueError):
            mgr.list_refunds(_admin_payload(), status="archived")

    def test_get_refund_by_id(self):
        mgr, cart, mkt, rid = self._setup()
        result = mgr.get_refund(rid)
        self.assertIsNotNone(result)
        self.assertEqual(result["request_id"], rid)

    def test_get_refund_unknown_returns_none(self):
        mgr = RefundManager()
        self.assertIsNone(mgr.get_refund("nope"))

    def test_get_my_refunds_pagination(self):
        order = _FakeOrder("o1", "u1", 100)
        cart = _FakeCartManager([order])
        mgr = RefundManager()
        mgr.request_refund("u1", "o1", "reason", cart)
        result = mgr.get_my_refunds("u1")
        self.assertEqual(result["total"], 1)


class TestRefundClawback(unittest.TestCase):
    """Refund approval must claw seller proceeds back so credits are conserved."""

    def _setup(self, seller_balance):
        # Buyer u1 bought a 500-credit item from seller s1.
        item = _FakeOrderItem(owner_id="s1", final_price=500)
        order = _FakeOrder("o1", "u1", 500, items=[item])
        cart = _FakeCartManager([order])
        mkt = _FakeMarketplace(credits={"u1": 0, "s1": seller_balance})
        mgr = RefundManager()
        mgr.request_refund("u1", "o1", "want refund", cart)
        rid = mgr.store.list_requests()["items"][0]["request_id"]
        return mgr, cart, mkt, rid

    def test_clawback_conserves_credits(self):
        # Seller has the full proceeds; refund must be money-neutral overall.
        mgr, cart, mkt, rid = self._setup(seller_balance=500)
        total_before = mkt._credits["u1"] + mkt._credits["s1"]
        result = mgr.approve_refund(_admin_payload(), rid, mkt, cart)
        self.assertEqual(mkt._credits["u1"], 500)   # buyer made whole
        self.assertEqual(mkt._credits["s1"], 0)     # seller clawed back
        self.assertEqual(result["reclaimed_from_sellers"], 500)
        self.assertEqual(mkt._credits["u1"] + mkt._credits["s1"], total_before)

    def test_clawback_records_sale_reversal_ledger(self):
        mgr, cart, mkt, rid = self._setup(seller_balance=500)
        mgr.approve_refund(_admin_payload(), rid, mkt, cart)
        entry = next(e for e in mkt._ledger if e["kind"] == "sale_reversal")
        self.assertEqual(entry["user_id"], "s1")
        self.assertEqual(entry["delta"], -500)

    def test_clawback_clamped_when_seller_spent_proceeds(self):
        # Seller only has 200 of the 500 left; clamp, platform absorbs 300.
        mgr, cart, mkt, rid = self._setup(seller_balance=200)
        result = mgr.approve_refund(_admin_payload(), rid, mkt, cart)
        self.assertEqual(mkt._credits["s1"], 0)        # not negative
        self.assertEqual(result["reclaimed_from_sellers"], 200)
        self.assertEqual(mkt._credits["u1"], 500)      # buyer still fully refunded

    def test_clamped_refund_books_platform_subsidy_and_conserves_total(self):
        # The 300 shortfall must be booked to the platform account so the
        # refund is zero-sum system-wide, not a silent credit injection.
        mgr, cart, mkt, rid = self._setup(seller_balance=200)
        total_before = sum(mkt._credits.values())
        mgr.approve_refund(_admin_payload(), rid, mkt, cart)
        total_after = sum(mkt._credits.values())
        self.assertEqual(total_after, total_before)        # conserved
        self.assertEqual(mkt._credits["__platform__"], -300)
        subsidy = next(e for e in mkt._ledger if e["kind"] == "refund_subsidy")
        self.assertEqual(subsidy["delta"], -300)

    def test_full_clawback_books_no_subsidy(self):
        mgr, cart, mkt, rid = self._setup(seller_balance=500)
        mgr.approve_refund(_admin_payload(), rid, mkt, cart)
        self.assertEqual(mkt._credits.get("__platform__", 0), 0)

    def test_clawback_multiple_sellers(self):
        items = [_FakeOrderItem("s1", 300), _FakeOrderItem("s2", 200)]
        order = _FakeOrder("o1", "u1", 500, items=items)
        cart = _FakeCartManager([order])
        mkt = _FakeMarketplace(credits={"u1": 0, "s1": 300, "s2": 200})
        mgr = RefundManager()
        mgr.request_refund("u1", "o1", "refund", cart)
        rid = mgr.store.list_requests()["items"][0]["request_id"]
        result = mgr.approve_refund(_admin_payload(), rid, mkt, cart)
        self.assertEqual(mkt._credits["s1"], 0)
        self.assertEqual(mkt._credits["s2"], 0)
        self.assertEqual(result["reclaimed_from_sellers"], 500)


class TestRefundConcurrency(unittest.TestCase):
    """Concurrent approvals must not double-refund (TOCTOU on status)."""

    def _setup(self, seller_balance=500):
        item = _FakeOrderItem(owner_id="s1", final_price=500)
        order = _FakeOrder("o1", "u1", 500, items=[item])
        cart = _FakeCartManager([order])
        mkt = _FakeMarketplace(credits={"u1": 0, "s1": seller_balance})
        mgr = RefundManager()
        mgr.request_refund("u1", "o1", "want refund", cart)
        rid = mgr.store.list_requests()["items"][0]["request_id"]
        return mgr, cart, mkt, rid

    def test_concurrent_approvals_refund_once(self):
        mgr, cart, mkt, rid = self._setup()
        n = 24
        barrier = threading.Barrier(n)
        successes = []
        failures = []
        lock = threading.Lock()

        def worker():
            barrier.wait()  # maximise contention on the claim
            try:
                mgr.approve_refund(_admin_payload(), rid, mkt, cart)
                with lock:
                    successes.append(1)
            except ValueError:
                with lock:
                    failures.append(1)

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly one approval may win; the buyer is refunded exactly once.
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), n - 1)
        self.assertEqual(mkt._credits["u1"], 500)   # not 500 * n
        self.assertEqual(mkt._credits["s1"], 0)

    def test_concurrent_approve_and_reject_one_wins(self):
        mgr, cart, mkt, rid = self._setup()
        results = []
        lock = threading.Lock()
        barrier = threading.Barrier(2)

        def do(fn):
            barrier.wait()
            try:
                fn()
                with lock:
                    results.append("ok")
            except ValueError:
                with lock:
                    results.append("err")

        t1 = threading.Thread(target=do, args=(lambda: mgr.approve_refund(_admin_payload(), rid, mkt, cart),))
        t2 = threading.Thread(target=do, args=(lambda: mgr.reject_refund(_admin_payload(), rid),))
        t1.start(); t2.start(); t1.join(); t2.join()
        # Exactly one of approve/reject wins.
        self.assertEqual(results.count("ok"), 1)
        # Buyer credited at most once (0 if reject won, 500 if approve won).
        self.assertIn(mkt._credits["u1"], (0, 500))


class TestRefundCrossChannelGuard(unittest.TestCase):
    """Order refund and listing dispute must not both refund one purchase."""

    def _setup(self):
        from avatar_marketplace import MarketplaceStore
        mkt = MarketplaceStore()
        mkt.add_credits("s1", 500)  # seller holds the sale proceeds
        item = _FakeOrderItem(owner_id="s1", final_price=500, listing_id="lst1")
        order = _FakeOrder("o1", "u1", 500, items=[item])
        cart = _FakeCartManager([order])
        mgr = RefundManager()
        mgr.request_refund("u1", "o1", "want refund", cart)
        rid = mgr.store.list_requests()["items"][0]["request_id"]
        return mgr, cart, mkt, rid

    def test_order_refund_skips_item_already_refunded_via_dispute(self):
        mgr, cart, mkt, rid = self._setup()
        # Simulate a listing dispute having already refunded this purchase.
        mkt.mark_purchase_refunded("u1", "lst1")
        result = mgr.approve_refund(_admin_payload(), rid, mkt, cart)
        # The already-refunded item is skipped: no double refund, no double claw.
        self.assertEqual(result["credits_returned"], 0)
        self.assertEqual(mkt.get_balance("u1"), 0)
        self.assertEqual(mkt.get_balance("s1"), 500)  # seller not clawed twice

    def test_order_refund_marks_purchase_so_dispute_is_blocked(self):
        mgr, cart, mkt, rid = self._setup()
        result = mgr.approve_refund(_admin_payload(), rid, mkt, cart)
        self.assertEqual(result["credits_returned"], 500)
        self.assertEqual(mkt.get_balance("u1"), 500)   # buyer refunded once
        # The purchase is now claimed, so a later dispute refund is blocked.
        self.assertTrue(mkt.is_purchase_refunded("u1", "lst1"))


class TestRefundManagerSingleton(unittest.TestCase):
    def test_singleton(self):
        a = get_refund_manager()
        b = get_refund_manager()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
