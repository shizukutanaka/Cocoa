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


class TestAdvertisedBenefitsAreReal(unittest.TestCase):
    """The product must not advertise a benefit it does not deliver (audit #92).

    Membership tiers define fee_discount_percent (Silver 5, Gold 10, Diamond
    15) and the profile page rendered it as a green "手数料 10% 割引" badge.
    But no platform fee is charged: both seller-credit sites pay the full
    price (avatar_marketplace.download, bundle_manager), and no pricing path
    anywhere reads fee_discount_percent. A user who spent 5,000 credits was
    shown a rebate on a fee nobody collects.

    Setting a fee RATE is a pricing decision and stays with the owner (§3-1).
    Not claiming a benefit that does not exist is not.

    PLATFORM_FEE_ENABLED is the single place that truth lives, so implementing
    a fee flips one constant and the badge becomes honest again by itself --
    which is what these tests hold in place.
    """

    def test_the_discount_is_inactive_while_no_fee_is_charged(self):
        import membership_manager as mm
        record = mm.MembershipRecord(user_id="u1", lifetime_credits=5_000)
        self.assertEqual(record.fee_discount_percent, 10, "tier table changed")
        payload = record.to_dict()
        self.assertFalse(
            payload["fee_discount_active"],
            "the UI is told the discount is active while no fee is taken",
        )
        self.assertEqual(
            payload["fee_discount_percent"], 10,
            "the tier's defined rate stays visible; only the CLAIM changes",
        )

    def test_the_flag_follows_the_fee_switch(self):
        # Implementing a fee must make the benefit real without any other edit.
        import unittest.mock as m
        import membership_manager as mm
        record = mm.MembershipRecord(user_id="u1", lifetime_credits=5_000)
        with m.patch.object(mm, "PLATFORM_FEE_ENABLED", True):
            self.assertTrue(record.to_dict()["fee_discount_active"])

    def test_bronze_has_nothing_to_claim_either_way(self):
        import unittest.mock as m
        import membership_manager as mm
        record = mm.MembershipRecord(user_id="u1", lifetime_credits=0)
        self.assertEqual(record.fee_discount_percent, 0)
        self.assertFalse(record.to_dict()["fee_discount_active"])
        with m.patch.object(mm, "PLATFORM_FEE_ENABLED", True):
            self.assertFalse(record.to_dict()["fee_discount_active"])

    def test_the_flag_matches_what_the_sale_path_actually_does(self):
        # The guard against the two drifting apart: if a fee is ever deducted,
        # the seller stops receiving the full price and this must be updated.
        import avatar_marketplace as market
        import membership_manager as mm
        store = market.MarketplaceStore()
        store.add_credits("buyer", 1000)
        listing = store.publish(
            avatar_id="a", owner_id="seller", owner_username="s", name="n",
            description="d", tags=[], category="other", parameters={"p": 1},
            price_credits=400, is_free=False,
        )
        store.download(listing.listing_id, "buyer")
        seller_got = store.get_balance("seller")
        if mm.PLATFORM_FEE_ENABLED:
            self.assertLess(seller_got, 400, "a fee is advertised but none is deducted")
        else:
            self.assertEqual(
                seller_got, 400,
                "the seller no longer receives the full price -- a fee exists, so "
                "set PLATFORM_FEE_ENABLED = True or the tier benefit stays hidden",
            )


class TestBundlePriceIsQuotedByTheServer(unittest.TestCase):
    """The advertised bundle price must be the price charged (audit #93).

    Bundle pricing lived in two places. The server discounts and floors PER
    ITEM inside purchase_bundle; the storefront fetched every constituent
    listing, summed the prices and floored ONCE. Those disagree whenever
    per-item flooring loses more:

        3 listings at 101, 10% off
          server:  3 * floor(101*0.9) = 3 * 90 = 270
          page:    floor(303 * 0.9)   = 272

    Measured against a live server before the fix: the page advertised 272 and
    the purchase took 270. Money stayed conserved -- the buyer paid exactly
    what the sellers received -- so no integrity check could have caught it.
    The defect was the shop window, and the cause was computing a price twice.

    Fixed by making the server quote it: BundleManager.item_price is the single
    definition, used by both quote() and purchase_bundle().
    """

    def _mgr_and_store(self):
        import avatar_marketplace as market
        from bundle_manager import BundleManager
        return BundleManager(), market.MarketplaceStore()

    def _bundle_of(self, mgr, store, prices, discount):
        listing_ids = []
        for i, price in enumerate(prices):
            lst = store.publish(
                avatar_id=f"a{i}", owner_id="seller", owner_username="s", name=f"n{i}",
                description="d", tags=[], category="other", parameters={"p": i},
                price_credits=price, is_free=False,
            )
            listing_ids.append(lst.listing_id)
        bundle = mgr.create_bundle(
            creator_id="seller", creator_username="s", name="b", description="d",
            listing_ids=listing_ids, discount_percent=discount,
            marketplace_store=store,
        )
        return bundle["bundle_id"]

    def test_the_quote_equals_what_the_purchase_charges(self):
        mgr, store = self._mgr_and_store()
        bundle_id = self._bundle_of(mgr, store, [101, 101, 101], 10)
        quoted = mgr.quote(bundle_id, store)["total_price"]

        store.add_credits("buyer", 5000)
        before = store.get_balance("buyer")
        mgr.purchase_bundle(bundle_id, "buyer", store)
        charged = before - store.get_balance("buyer")

        self.assertEqual(quoted, charged, "the advertised price is not the charged price")
        self.assertEqual(charged, 270, "per-item flooring changed")

    def test_the_quote_is_not_the_discount_applied_to_the_sum(self):
        # The specific arithmetic that used to be on the page. If a future
        # change adopts it, the quote and the charge silently diverge again.
        mgr, store = self._mgr_and_store()
        bundle_id = self._bundle_of(mgr, store, [101, 101, 101], 10)
        quoted = mgr.quote(bundle_id, store)["total_price"]
        floor_of_sum = (303 * 90) // 100
        self.assertEqual(floor_of_sum, 272)
        self.assertNotEqual(quoted, floor_of_sum)

    def test_the_seller_receives_exactly_what_the_buyer_paid(self):
        mgr, store = self._mgr_and_store()
        bundle_id = self._bundle_of(mgr, store, [101, 101, 101], 10)
        store.add_credits("buyer", 5000)
        buyer_before, seller_before = store.get_balance("buyer"), store.get_balance("seller")
        mgr.purchase_bundle(bundle_id, "buyer", store)
        paid = buyer_before - store.get_balance("buyer")
        received = store.get_balance("seller") - seller_before
        self.assertEqual(paid, received, "a bundle purchase created or destroyed credits")

    def test_the_quote_reports_the_saving_against_the_undiscounted_total(self):
        mgr, store = self._mgr_and_store()
        bundle_id = self._bundle_of(mgr, store, [101, 101, 101], 10)
        quote = mgr.quote(bundle_id, store)
        self.assertEqual(quote["original_total"], 303)
        self.assertEqual(quote["savings"], 303 - quote["total_price"])

    def test_a_free_listing_costs_nothing_in_a_bundle(self):
        import avatar_marketplace as market
        from bundle_manager import BundleManager
        mgr, store = BundleManager(), market.MarketplaceStore()
        free = store.publish(
            avatar_id="f", owner_id="seller", owner_username="s", name="free",
            description="d", tags=[], category="other", parameters={"p": 1},
        )
        paid = store.publish(
            avatar_id="p", owner_id="seller", owner_username="s", name="paid",
            description="d", tags=[], category="other", parameters={"p": 2},
            price_credits=200, is_free=False,
        )
        bundle = mgr.create_bundle(
            creator_id="seller", creator_username="s", name="b", description="d",
            listing_ids=[free.listing_id, paid.listing_id], discount_percent=50,
            marketplace_store=store,
        )
        self.assertEqual(mgr.quote(bundle["bundle_id"], store)["total_price"], 100)


if __name__ == "__main__":
    unittest.main()