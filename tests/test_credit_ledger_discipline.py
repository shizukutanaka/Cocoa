"""Every credit mutation must go through a ledgered primitive (audit #90).

Why this is a test and not a comment
------------------------------------
`verify_ledger_integrity` asserts that each balance equals the sum of its
ledger entries. That invariant is load-bearing well beyond accounting: the
restore path refuses to start when it fails (#74), the concurrency suite
asserts it survives parallel purchases (#81), and the admin console reports it
live (#82). All of that is only meaningful while every write to a balance also
writes a ledger entry.

An audit of the store found the discipline intact -- three assignment sites,
all inside `_credit_locked` / `_debit_locked` / `_subsidize_locked` -- but an
audit is a statement about one moment. The obvious way to break it is to add a
new way for money to enter the system, which is exactly what integrating real
payments (§3-1) would do. This test is the guard for that change: a handler
that credits a user directly after a successful charge would pass every
behavioural test in the suite and silently create money the ledger has never
seen.

It is structural on purpose. A behavioural test cannot catch "some future code
path bypasses the ledger", because the path does not exist yet.
"""
import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "main"))

MARKETPLACE = REPO_ROOT / "main" / "avatar_marketplace.py"

# The only functions permitted to assign to a balance. Each appends a matching
# ledger entry before returning.
LEDGERED_PRIMITIVES = {"_credit_locked", "_debit_locked", "_subsidize_locked"}


def _enclosing_function(tree, target_node):
    """Name of the function containing `target_node`, or None at module level."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if child is target_node:
                    return node.name
    return None


class TestOnlyLedgeredPrimitivesMoveMoney(unittest.TestCase):
    def setUp(self):
        self.source = MARKETPLACE.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def _balance_assignments(self):
        """Every `self._credits[...] = ...` in the store, with its function."""
        found = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "_credits"
                ):
                    found.append((_enclosing_function(self.tree, node), node.lineno))
        return found

    def test_every_balance_write_lives_in_a_ledgered_primitive(self):
        offenders = [
            (fn, line) for fn, line in self._balance_assignments()
            if fn not in LEDGERED_PRIMITIVES
        ]
        self.assertEqual(
            offenders, [],
            "a balance is written outside the ledgered primitives "
            f"{sorted(LEDGERED_PRIMITIVES)}: {offenders}. Money must not enter or "
            "leave the system without a ledger entry -- route it through "
            "_credit_locked / _debit_locked / _subsidize_locked instead.",
        )

    def test_the_primitives_still_exist_and_are_actually_used(self):
        # Guards against the test passing vacuously if the primitives are
        # renamed away and every write becomes "outside" nothing.
        assignments = self._balance_assignments()
        self.assertTrue(assignments, "no balance assignments found -- has the store moved?")
        self.assertEqual(
            {fn for fn, _ in assignments}, LEDGERED_PRIMITIVES,
            "the set of functions writing balances changed; if that is "
            "deliberate, update LEDGERED_PRIMITIVES and say why in the audit",
        )

    def test_each_primitive_appends_to_the_ledger(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name in LEDGERED_PRIMITIVES:
                calls = {
                    getattr(c.func, "attr", None)
                    for c in ast.walk(node) if isinstance(c, ast.Call)
                }
                self.assertIn(
                    "_append_ledger", calls,
                    f"{node.name} writes a balance without appending a ledger entry",
                )


class TestMembershipIsNotASecondWallet(unittest.TestCase):
    """membership_manager also has add_credits/subtract_credits.

    It tracks `lifetime_credits`, a cumulative spend counter that decides fee
    tiers -- deliberately NOT a spendable balance, so it is correctly outside
    the ledger. Pinning that here because the name collision invites a future
    reader to "fix" the inconsistency by wiring it into the money path, or to
    spend from it.
    """

    def test_membership_tracks_a_counter_not_a_balance(self):
        from membership_manager import MembershipRecord
        record = MembershipRecord(user_id="u1")
        self.assertTrue(hasattr(record, "lifetime_credits"))
        self.assertFalse(
            hasattr(record, "balance"),
            "membership must not hold a spendable balance; money lives in the "
            "marketplace store's ledgered _credits",
        )

    def test_lifetime_credits_only_grows_by_recorded_purchases(self):
        from membership_manager import MembershipStore
        store = MembershipStore()
        store.add_credits("u1", 300)
        self.assertEqual(store.get_or_create("u1").lifetime_credits, 300)
        store.subtract_credits("u1", 300)  # what a refund does
        self.assertEqual(
            store.get_or_create("u1").lifetime_credits, 0,
            "a refunded purchase must not leave lifetime credit behind, or it "
            "buys a permanent fee discount",
        )


class TestEarningsNetOutReversals(unittest.TestCase):
    """What a creator is OWED must track what they actually kept (audit #91).

    Measured before the fix: a 400-credit sale was refunded, the seller's
    balance was correctly clawed back to its starting value, and both
    `total_credits_earned` and the earnings summary still reported 400. A
    payout computed from either figure would have paid for a sale that was
    refunded.

    Two separate causes, one symptom:
      * get_earnings_summary read the ledger but summed only the positive
        kinds, ignoring the sale_reversal / dispute_reversal entries sitting
        right next to them
      * get_creator_analytics summed amount_paid from the DOWNLOAD LOG, which
        keeps a refunded sale's entry and is also capped (#78), so a
        long-lived creator's revenue would silently shrink as old sales aged
        out

    Sending money is the owner's decision (§3-2); the number that decides how
    much is not.
    """

    def _sold_then_refunded(self):
        import avatar_marketplace as market
        store = market.MarketplaceStore()
        store.add_credits("buyer", 1000)
        listing = store.publish(
            avatar_id="a", owner_id="seller", owner_username="s", name="n",
            description="d", tags=[], category="other", parameters={"p": 1},
            price_credits=400, is_free=False,
        )
        store.download(listing.listing_id, "buyer")
        return store, listing

    def test_a_refunded_sale_is_not_still_owed(self):
        store, listing = self._sold_then_refunded()
        self.assertEqual(store.get_balance("seller"), 400)
        self.assertEqual(store.get_earnings_summary("seller")["total_earned"], 400)

        # What refund_manager does to the seller on approval.
        with store._lock:
            store._debit_locked("seller", 400, "sale_reversal", ref_id="order1")

        self.assertEqual(store.get_balance("seller"), 0)
        summary = store.get_earnings_summary("seller")
        self.assertEqual(summary["total_earned"], 0, "a refunded sale is still counted as owed")
        self.assertEqual(summary["reversed_credits"], 400)
        self.assertEqual(summary["gross_earned"], 400, "gross must stay visible for analytics")
        self.assertEqual(
            store.get_creator_analytics("seller")["total_credits_earned"], 0,
            "analytics revenue must net the refund too",
        )

    def test_a_dispute_resolved_against_the_seller_also_nets_out(self):
        store, _ = self._sold_then_refunded()
        with store._lock:
            store._debit_locked("seller", 400, "dispute_reversal", ref_id="dispute1")
        self.assertEqual(store.get_earnings_summary("seller")["total_earned"], 0)

    def test_earnings_survive_download_log_trimming(self):
        # The log is capped (#78); the ledger is not. Revenue must come from
        # the ledger, or a busy creator's history silently erases their sales.
        store, _ = self._sold_then_refunded()
        before = store.get_creator_analytics("seller")["total_credits_earned"]
        with store._lock:
            store._download_log.clear()  # what the cap eventually does
        after = store.get_creator_analytics("seller")["total_credits_earned"]
        self.assertEqual(before, after, "revenue changed when the download log was trimmed")
        self.assertEqual(after, 400)

    def test_earnings_still_count_tips_and_gifts(self):
        store, _ = self._sold_then_refunded()
        with store._lock:
            store._credit_locked("seller", 50, "tip_received", ref_id="fan")
        summary = store.get_earnings_summary("seller")
        self.assertEqual(summary["tips_and_gifts_received"], 50)
        self.assertEqual(summary["total_earned"], 450)


if __name__ == "__main__":
    unittest.main()