"""Tests for main/referral_manager.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from referral_manager import (
    REFERRAL_BONUS_CREDITS,
    ReferralManager,
    ReferralRecord,
    ReferralStore,
    get_referral_manager,
)


def _make_manager() -> ReferralManager:
    return ReferralManager(ReferralStore())


class _FakeMarketplace:
    def __init__(self) -> None:
        self._credits: dict = {}
        self._grants: list = []
        self._ledger: list = []

    def add_credits(self, user_id: str, amount: int) -> int:
        self._credits[user_id] = self._credits.get(user_id, 0) + amount
        self._grants.append((user_id, amount))
        self._ledger.append({"user_id": user_id, "amount": amount, "kind": "grant", "ref_id": ""})
        return self._credits[user_id]

    def credit(self, user_id: str, amount: int, kind: str, ref_id: str = "") -> int:
        if amount <= 0:
            raise ValueError("amount must be positive")
        self._credits[user_id] = self._credits.get(user_id, 0) + amount
        self._ledger.append({"user_id": user_id, "amount": amount, "kind": kind, "ref_id": ref_id})
        return self._credits[user_id]


class TestReferralRecord(unittest.TestCase):
    def test_to_dict(self):
        r = ReferralRecord("rid", "ref1", "new1", "ABCD1234")
        d = r.to_dict()
        self.assertEqual(d["referral_id"], "rid")
        self.assertEqual(d["status"], "pending")
        self.assertIsNone(d["converted_at"])
        self.assertEqual(d["bonus_awarded"], 0)


class TestReferralStore(unittest.TestCase):
    def setUp(self):
        self.store = ReferralStore()

    def test_get_or_create_code_returns_string(self):
        code = self.store.get_or_create_code("u1")
        self.assertIsInstance(code, str)
        self.assertTrue(len(code) > 0)

    def test_same_user_same_code(self):
        c1 = self.store.get_or_create_code("u1")
        c2 = self.store.get_or_create_code("u1")
        self.assertEqual(c1, c2)

    def test_different_users_different_codes(self):
        c1 = self.store.get_or_create_code("u1")
        c2 = self.store.get_or_create_code("u2")
        self.assertNotEqual(c1, c2)

    def test_get_code_owner(self):
        code = self.store.get_or_create_code("u1")
        self.assertEqual(self.store.get_code_owner(code), "u1")

    def test_get_code_owner_case_insensitive(self):
        code = self.store.get_or_create_code("u1")
        self.assertEqual(self.store.get_code_owner(code.lower()), "u1")

    def test_get_code_owner_unknown_returns_none(self):
        self.assertIsNone(self.store.get_code_owner("XXXXXXXX"))

    def test_create_referral(self):
        code = self.store.get_or_create_code("ref1")
        record = self.store.create_referral("ref1", "new1", code)
        self.assertEqual(record.referrer_id, "ref1")
        self.assertEqual(record.referred_id, "new1")
        self.assertEqual(record.status, "pending")

    def test_create_referral_duplicate_raises(self):
        code = self.store.get_or_create_code("ref1")
        self.store.create_referral("ref1", "new1", code)
        with self.assertRaises(ValueError):
            self.store.create_referral("ref1", "new1", code)

    def test_convert_referral(self):
        code = self.store.get_or_create_code("ref1")
        self.store.create_referral("ref1", "new1", code)
        result = self.store.convert_referral("new1", 50)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "converted")
        self.assertEqual(result.bonus_awarded, 50)
        self.assertIsNotNone(result.converted_at)

    def test_convert_non_existent_returns_none(self):
        self.assertIsNone(self.store.convert_referral("no-user", 50))

    def test_convert_already_converted_returns_none(self):
        code = self.store.get_or_create_code("ref1")
        self.store.create_referral("ref1", "new1", code)
        self.store.convert_referral("new1", 50)
        self.assertIsNone(self.store.convert_referral("new1", 50))

    def test_get_referral_by_referred(self):
        code = self.store.get_or_create_code("ref1")
        self.store.create_referral("ref1", "new1", code)
        record = self.store.get_referral_by_referred("new1")
        self.assertIsNotNone(record)

    def test_get_referral_by_referred_none_if_not_referred(self):
        self.assertIsNone(self.store.get_referral_by_referred("orphan"))

    def test_get_referrals_by_referrer_pagination(self):
        code = self.store.get_or_create_code("ref1")
        for i in range(5):
            self.store.create_referral("ref1", f"new{i}", code)
            # Reset so duplicate check doesn't fire
            del self.store._referred_by[f"new{i}"]
            self.store._referred_by[f"new{i}"] = list(self.store._referrer_records["ref1"])[-1]
        result = self.store.get_referrals_by_referrer("ref1", limit=3, offset=0)
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["items"]), 3)
        self.assertTrue(result["has_more"])

    def test_get_referral_stats(self):
        code = self.store.get_or_create_code("ref1")
        self.store.create_referral("ref1", "new1", code)
        self.store.convert_referral("new1", 50)
        self.store.create_referral("ref1", "new2", code)
        stats = self.store.get_referral_stats("ref1")
        self.assertEqual(stats["total_referrals"], 2)
        self.assertEqual(stats["converted"], 1)
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["total_bonus_earned"], 50)


class TestReferralManager(unittest.TestCase):
    def setUp(self):
        self.mgr = _make_manager()
        self.mp = _FakeMarketplace()

    def test_get_my_code_returns_code(self):
        code = self.mgr.get_my_code("u1")
        self.assertIsInstance(code, str)
        self.assertTrue(len(code) > 0)

    def test_apply_valid_code(self):
        code = self.mgr.get_my_code("ref1")
        record = self.mgr.apply_referral_code("new1", code)
        self.assertIsNotNone(record)
        self.assertEqual(record.referrer_id, "ref1")

    def test_apply_invalid_code_returns_none(self):
        result = self.mgr.apply_referral_code("new1", "BADCODE")
        self.assertIsNone(result)

    def test_apply_empty_code_returns_none(self):
        result = self.mgr.apply_referral_code("new1", "")
        self.assertIsNone(result)

    def test_apply_own_code_raises(self):
        code = self.mgr.get_my_code("u1")
        with self.assertRaises(ValueError):
            self.mgr.apply_referral_code("u1", code)

    def test_apply_code_twice_silently_ignores(self):
        code = self.mgr.get_my_code("ref1")
        self.mgr.apply_referral_code("new1", code)
        result = self.mgr.apply_referral_code("new1", code)
        self.assertIsNone(result)

    def test_on_first_purchase_awards_bonus(self):
        code = self.mgr.get_my_code("ref1")
        self.mgr.apply_referral_code("new1", code)
        record = self.mgr.on_first_purchase("new1", self.mp)
        self.assertIsNotNone(record)
        self.assertEqual(record.status, "converted")
        self.assertEqual(record.bonus_awarded, REFERRAL_BONUS_CREDITS)
        self.assertEqual(self.mp._credits.get("ref1", 0), REFERRAL_BONUS_CREDITS)

    def test_on_first_purchase_records_referral_bonus_ledger_kind(self):
        # Bonus must be auditable as "referral_bonus", not generic "grant".
        code = self.mgr.get_my_code("ref1")
        self.mgr.apply_referral_code("new1", code)
        self.mgr.on_first_purchase("new1", self.mp)
        entry = next(e for e in self.mp._ledger if e["user_id"] == "ref1")
        self.assertEqual(entry["kind"], "referral_bonus")
        self.assertEqual(entry["ref_id"], "new1")

    def test_on_first_purchase_no_referral_returns_none(self):
        result = self.mgr.on_first_purchase("orphan", self.mp)
        self.assertIsNone(result)

    def test_on_first_purchase_twice_only_converts_once(self):
        code = self.mgr.get_my_code("ref1")
        self.mgr.apply_referral_code("new1", code)
        self.mgr.on_first_purchase("new1", self.mp)
        result = self.mgr.on_first_purchase("new1", self.mp)
        self.assertIsNone(result)
        bonuses = [e for e in self.mp._ledger if e["kind"] == "referral_bonus"]
        self.assertEqual(len(bonuses), 1)

    def test_get_my_referrals_empty(self):
        result = self.mgr.get_my_referrals("ref1")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])

    def test_get_my_stats_empty(self):
        stats = self.mgr.get_my_stats("ref1")
        self.assertEqual(stats["total_referrals"], 0)
        self.assertEqual(stats["converted"], 0)

    def test_get_my_referral_info_none_if_no_referral(self):
        self.assertIsNone(self.mgr.get_my_referral_info("orphan"))

    def test_get_my_referral_info_returns_dict(self):
        code = self.mgr.get_my_code("ref1")
        self.mgr.apply_referral_code("new1", code)
        info = self.mgr.get_my_referral_info("new1")
        self.assertIsNotNone(info)
        self.assertEqual(info["referrer_id"], "ref1")


class TestReferralSingleton(unittest.TestCase):
    def test_singleton(self):
        a = get_referral_manager()
        b = get_referral_manager()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
