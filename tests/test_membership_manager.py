"""Tests for main/membership_manager.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from membership_manager import (
    MembershipManager,
    MembershipRecord,
    MembershipStore,
    _compute_tier,
    get_membership_manager,
)


def _admin():
    return {"sub": "admin1", "role": "admin"}


def _user():
    return {"sub": "u1", "role": "user"}


class TestComputeTier(unittest.TestCase):
    def test_zero_credits_is_bronze(self):
        self.assertEqual(_compute_tier(0)[0], "bronze")

    def test_999_is_bronze(self):
        self.assertEqual(_compute_tier(999)[0], "bronze")

    def test_1000_is_silver(self):
        self.assertEqual(_compute_tier(1000)[0], "silver")

    def test_4999_is_silver(self):
        self.assertEqual(_compute_tier(4999)[0], "silver")

    def test_5000_is_gold(self):
        self.assertEqual(_compute_tier(5000)[0], "gold")

    def test_19999_is_gold(self):
        self.assertEqual(_compute_tier(19999)[0], "gold")

    def test_20000_is_diamond(self):
        self.assertEqual(_compute_tier(20000)[0], "diamond")

    def test_very_large_is_diamond(self):
        self.assertEqual(_compute_tier(999_999)[0], "diamond")


class TestMembershipRecord(unittest.TestCase):
    def test_default_tier_bronze(self):
        rec = MembershipRecord(user_id="u1")
        self.assertEqual(rec.tier, "bronze")
        self.assertEqual(rec.fee_discount_percent, 0)

    def test_silver_discount(self):
        rec = MembershipRecord(user_id="u1", lifetime_credits=1000)
        self.assertEqual(rec.tier, "silver")
        self.assertEqual(rec.fee_discount_percent, 5)

    def test_gold_discount(self):
        rec = MembershipRecord(user_id="u1", lifetime_credits=5000)
        self.assertEqual(rec.fee_discount_percent, 10)

    def test_diamond_discount(self):
        rec = MembershipRecord(user_id="u1", lifetime_credits=20000)
        self.assertEqual(rec.fee_discount_percent, 15)

    def test_next_tier_threshold_bronze(self):
        rec = MembershipRecord(user_id="u1", lifetime_credits=500)
        self.assertEqual(rec.next_tier_threshold, 1000)

    def test_credits_to_next_tier_bronze(self):
        rec = MembershipRecord(user_id="u1", lifetime_credits=600)
        self.assertEqual(rec.credits_to_next_tier, 400)

    def test_no_next_tier_for_diamond(self):
        rec = MembershipRecord(user_id="u1", lifetime_credits=20000)
        self.assertIsNone(rec.next_tier_threshold)
        self.assertIsNone(rec.credits_to_next_tier)

    def test_to_dict_keys(self):
        rec = MembershipRecord(user_id="u1", lifetime_credits=1500)
        d = rec.to_dict()
        for key in ("user_id", "lifetime_credits", "tier", "tier_label",
                    "fee_discount_percent", "next_tier_threshold",
                    "credits_to_next_tier", "updated_at"):
            self.assertIn(key, d)

    def test_tier_label_silver(self):
        rec = MembershipRecord(user_id="u1", lifetime_credits=1000)
        self.assertEqual(rec.tier_label, "Silver")


class TestMembershipStore(unittest.TestCase):
    def setUp(self):
        self.store = MembershipStore()

    def test_get_or_create_new(self):
        rec = self.store.get_or_create("u1")
        self.assertEqual(rec.user_id, "u1")
        self.assertEqual(rec.lifetime_credits, 0)

    def test_get_or_create_idempotent(self):
        r1 = self.store.get_or_create("u1")
        r2 = self.store.get_or_create("u1")
        self.assertIs(r1, r2)

    def test_add_credits_increases_lifetime(self):
        rec = self.store.add_credits("u1", 500)
        self.assertEqual(rec.lifetime_credits, 500)
        rec2 = self.store.add_credits("u1", 600)
        self.assertEqual(rec2.lifetime_credits, 1100)

    def test_add_credits_zero_raises(self):
        with self.assertRaises(ValueError):
            self.store.add_credits("u1", 0)

    def test_add_credits_negative_raises(self):
        with self.assertRaises(ValueError):
            self.store.add_credits("u1", -50)

    def test_subtract_credits_decreases_lifetime(self):
        self.store.add_credits("u1", 1000)
        rec = self.store.subtract_credits("u1", 400)
        self.assertEqual(rec.lifetime_credits, 600)

    def test_subtract_credits_clamps_at_zero(self):
        self.store.add_credits("u1", 300)
        rec = self.store.subtract_credits("u1", 999)
        self.assertEqual(rec.lifetime_credits, 0)

    def test_subtract_credits_zero_raises(self):
        with self.assertRaises(ValueError):
            self.store.subtract_credits("u1", 0)

    def test_subtract_credits_can_downgrade_tier(self):
        self.store.add_credits("u1", 5000)            # gold
        self.assertEqual(self.store.get_or_create("u1").tier, "gold")
        self.store.subtract_credits("u1", 5000)       # refunded → bronze
        self.assertEqual(self.store.get_or_create("u1").tier, "bronze")

    def test_adjust_credits_sets_exact(self):
        self.store.add_credits("u1", 100)
        rec = self.store.adjust_credits("u1", 3000)
        self.assertEqual(rec.lifetime_credits, 3000)

    def test_adjust_credits_negative_raises(self):
        with self.assertRaises(ValueError):
            self.store.adjust_credits("u1", -1)

    def test_list_by_tier_all(self):
        self.store.add_credits("u1", 100)
        self.store.add_credits("u2", 1500)
        result = self.store.list_by_tier()
        self.assertEqual(result["total"], 2)

    def test_list_by_tier_filter(self):
        self.store.add_credits("u1", 100)
        self.store.add_credits("u2", 1500)
        result = self.store.list_by_tier(tier="silver")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["user_id"], "u2")

    def test_list_sorted_by_lifetime_desc(self):
        self.store.add_credits("u1", 100)
        self.store.add_credits("u2", 5000)
        result = self.store.list_by_tier()
        self.assertEqual(result["items"][0]["user_id"], "u2")

    def test_list_pagination(self):
        for i in range(5):
            self.store.add_credits(f"u{i}", 100 * (i + 1))
        result = self.store.list_by_tier(limit=2, offset=0)
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["items"]), 2)
        self.assertTrue(result["has_more"])

    def test_tier_distribution(self):
        self.store.add_credits("u1", 100)   # bronze
        self.store.add_credits("u2", 1500)  # silver
        self.store.add_credits("u3", 5000)  # gold
        dist = self.store.get_tier_distribution()
        self.assertEqual(dist["bronze"], 1)
        self.assertEqual(dist["silver"], 1)
        self.assertEqual(dist["gold"], 1)
        self.assertEqual(dist["diamond"], 0)


class TestMembershipManager(unittest.TestCase):
    def setUp(self):
        self.mgr = MembershipManager()

    def test_get_membership_new_user(self):
        result = self.mgr.get_membership("u1")
        self.assertEqual(result["tier"], "bronze")
        self.assertEqual(result["lifetime_credits"], 0)

    def test_record_purchase_upgrades_tier(self):
        self.mgr.record_purchase("u1", 500)
        result = self.mgr.record_purchase("u1", 600)
        self.assertEqual(result["tier"], "silver")
        self.assertEqual(result["lifetime_credits"], 1100)

    def test_record_purchase_zero_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.record_purchase("u1", 0)

    def test_record_refund_reverses_tier_farming(self):
        # Buy 5000 → gold; refund 5000 → back to bronze (net spend 0, no
        # permanent tier promotion).
        self.mgr.record_purchase("u1", 5000)
        self.assertEqual(self.mgr.get_membership("u1")["tier"], "gold")
        result = self.mgr.record_refund("u1", 5000)
        self.assertEqual(result["tier"], "bronze")
        self.assertEqual(result["lifetime_credits"], 0)

    def test_record_refund_partial(self):
        self.mgr.record_purchase("u1", 5000)
        self.mgr.record_purchase("u1", 1000)   # lifetime 6000, gold
        self.mgr.record_refund("u1", 5000)     # refund one → lifetime 1000, silver
        result = self.mgr.get_membership("u1")
        self.assertEqual(result["lifetime_credits"], 1000)
        self.assertEqual(result["tier"], "silver")

    def test_record_refund_zero_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.record_refund("u1", 0)

    def test_get_fee_discount_new_user(self):
        self.assertEqual(self.mgr.get_fee_discount("u1"), 0)

    def test_get_fee_discount_gold(self):
        self.mgr.record_purchase("u1", 5000)
        self.assertEqual(self.mgr.get_fee_discount("u1"), 10)

    def test_admin_adjust_sets_lifetime(self):
        result = self.mgr.admin_adjust(_admin(), "u1", 20000)
        self.assertEqual(result["tier"], "diamond")

    def test_admin_adjust_non_admin_raises(self):
        with self.assertRaises(PermissionError):
            self.mgr.admin_adjust(_user(), "u1", 1000)

    def test_admin_adjust_negative_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.admin_adjust(_admin(), "u1", -1)

    def test_list_members_admin(self):
        self.mgr.record_purchase("u1", 100)
        self.mgr.record_purchase("u2", 2000)
        result = self.mgr.list_members(_admin())
        self.assertEqual(result["total"], 2)

    def test_list_members_non_admin_raises(self):
        with self.assertRaises(PermissionError):
            self.mgr.list_members(_user())

    def test_list_members_invalid_tier_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.list_members(_admin(), tier="platinum")

    def test_list_members_filter_tier(self):
        self.mgr.record_purchase("u1", 100)    # bronze
        self.mgr.record_purchase("u2", 5000)   # gold
        result = self.mgr.list_members(_admin(), tier="gold")
        self.assertEqual(result["total"], 1)

    def test_tier_distribution_admin(self):
        self.mgr.record_purchase("u1", 100)
        dist = self.mgr.tier_distribution(_admin())
        self.assertIn("bronze", dist)
        self.assertEqual(dist["bronze"], 1)

    def test_tier_distribution_non_admin_raises(self):
        with self.assertRaises(PermissionError):
            self.mgr.tier_distribution(_user())


class TestMembershipPaginationClamp(unittest.TestCase):
    def setUp(self):
        self.store = MembershipStore()
        for i in range(5):
            self.store.add_credits(f"u{i}", 100)

    def test_negative_offset_clamped(self):
        r = self.store.list_by_tier(offset=-2, limit=2)
        self.assertEqual(r["offset"], 0)

    def test_zero_limit_clamped(self):
        r = self.store.list_by_tier(offset=0, limit=0)
        self.assertGreaterEqual(r["limit"], 1)

    def test_huge_limit_capped(self):
        r = self.store.list_by_tier(offset=0, limit=10**9)
        self.assertLessEqual(r["limit"], 100)


class TestMembershipManagerSingleton(unittest.TestCase):
    def test_singleton(self):
        a = get_membership_manager()
        b = get_membership_manager()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
