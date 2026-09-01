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


if __name__ == "__main__":
    unittest.main()
