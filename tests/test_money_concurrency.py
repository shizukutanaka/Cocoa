"""Concurrency invariants on the money path (FEATURE_AUDIT #81).

A marketplace's worst failure mode is not a crash, it is arithmetic that is
wrong under load: a buyer spending the same credits twice, a limited listing
overselling, or a refund paying out more than once. None of these show up in
sequential tests, and none had ever been probed here.

Probed against a live server first -- 5 concurrent purchases with only enough
credit for one, 8 concurrent buyers on stock_limit=1, and 6 concurrent
approvals of a single refund. All three held: one winner each, balances exact,
and no credits created.

WHAT THESE TESTS DO AND DO NOT PROVE
------------------------------------
They assert the INVARIANTS (exactly one winner; the credit supply is
unchanged; the ledger still agrees with the balances). They do NOT prove the
store's locking works, and it is worth being precise about that: replacing
MarketplaceStore._lock with a no-op context manager and rerunning under
sys.setswitchinterval(1e-6) still produces one winner every time, because
CPython's GIL happens not to yield inside these short critical sections.

So these are a guard against a change that breaks the arithmetic -- a
read-modify-write straddling an await, an I/O call added inside a critical
section, a refactor that drops a debit -- and not a guard against the lock
being deleted. Anyone tightening this should widen the critical section or
move to true parallelism rather than trusting a green run here to mean the
locking is sound.
"""
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "main"))

import avatar_marketplace as market  # noqa: E402


def run_concurrently(fn, count):
    """Fire `fn(i)` on `count` threads released as close to together as possible."""
    start = threading.Barrier(count)
    results = []
    lock = threading.Lock()

    def worker(i):
        start.wait()
        try:
            outcome = ("ok", fn(i))
        except Exception as e:
            outcome = ("err", type(e).__name__)
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return results


class TestNoDoubleSpend(unittest.TestCase):
    def test_a_buyer_cannot_spend_the_same_credits_twice(self):
        store = market.MarketplaceStore()
        store.add_credits("buyer", 100)
        listings = [
            store.publish(
                avatar_id=f"a{i}", owner_id="seller", owner_username="s", name=f"n{i}",
                description="d", tags=[], category="other", parameters={"p": i},
                price_credits=100, is_free=False,
            )
            for i in range(5)
        ]
        # Five different listings, each costing the buyer's ENTIRE balance.
        results = run_concurrently(
            lambda i: store.download(listings[i].listing_id, "buyer"), 5
        )
        succeeded = [r for r in results if r[0] == "ok" and r[1] is not None]
        self.assertEqual(len(succeeded), 1, f"double-spend: {len(succeeded)} purchases went through")
        self.assertEqual(store.get_balance("buyer"), 0)
        self.assertEqual(store.get_balance("seller"), 100)


class TestNoOversell(unittest.TestCase):
    def test_a_one_copy_listing_sells_exactly_once(self):
        store = market.MarketplaceStore()
        listing = store.publish(
            avatar_id="a", owner_id="seller", owner_username="s", name="n",
            description="d", tags=[], category="other", parameters={"p": 1},
            price_credits=10, is_free=False,
        )
        store.set_stock_limit(listing.listing_id, "seller", 1)
        for i in range(8):
            store.add_credits(f"buyer{i}", 100)

        results = run_concurrently(
            lambda i: store.download(listing.listing_id, f"buyer{i}"), 8
        )
        succeeded = [r for r in results if r[0] == "ok" and r[1] is not None]
        self.assertEqual(len(succeeded), 1, f"oversold: {len(succeeded)} buyers got the only copy")
        refreshed = store.get_listing(listing.listing_id)
        self.assertEqual(refreshed.stock_remaining, 0)
        self.assertGreaterEqual(refreshed.stock_remaining, 0, "stock went negative")
        # Exactly one buyer paid.
        self.assertEqual(store.get_balance("seller"), 10)


class TestCreditsAreConserved(unittest.TestCase):
    """Whatever happens concurrently, the total credit supply must not change."""

    def test_concurrent_purchases_never_create_or_destroy_credits(self):
        store = market.MarketplaceStore()
        for i in range(6):
            store.add_credits(f"buyer{i}", 50)
        supply_before = sum(store.get_balance(f"buyer{i}") for i in range(6))
        listings = [
            store.publish(
                avatar_id=f"a{i}", owner_id="seller", owner_username="s", name=f"n{i}",
                description="d", tags=[], category="other", parameters={"p": i},
                price_credits=30, is_free=False,
            )
            for i in range(6)
        ]
        run_concurrently(lambda i: store.download(listings[i].listing_id, f"buyer{i}"), 6)

        supply_after = (
            sum(store.get_balance(f"buyer{i}") for i in range(6))
            + store.get_balance("seller")
        )
        self.assertEqual(
            supply_after, supply_before,
            f"credit supply changed under concurrency: {supply_before} -> {supply_after}",
        )

    def test_the_ledger_still_agrees_with_the_balances_after_a_concurrent_run(self):
        # This is the same invariant a restored snapshot is checked against
        # (#71), so a concurrency bug here would also poison durability.
        store = market.MarketplaceStore()
        for i in range(6):
            store.add_credits(f"buyer{i}", 100)
        listings = [
            store.publish(
                avatar_id=f"a{i}", owner_id="seller", owner_username="s", name=f"n{i}",
                description="d", tags=[], category="other", parameters={"p": i},
                price_credits=25, is_free=False,
            )
            for i in range(6)
        ]
        run_concurrently(lambda i: store.download(listings[i].listing_id, f"buyer{i}"), 6)

        discrepancies, _ = store._ledger_discrepancies(store._credits, store._credit_ledger)
        self.assertEqual(discrepancies, [], f"ledger disagrees with balances: {discrepancies}")


if __name__ == "__main__":
    unittest.main()
