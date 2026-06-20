"""Tests for main/gift_card_manager.py"""
import sys
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gift_card_manager import (
    GiftCard,
    GiftCardManager,
    GiftCardStore,
    _MAX_AMOUNT,
    _MAX_VOUCHERS_PER_USER,
    get_gift_card_manager,
)


def _make_store() -> GiftCardStore:
    return GiftCardStore()


class _FakeMarketplace:
    """Minimal marketplace stub with credits and ledger."""

    def __init__(self):
        self._lock = threading.Lock()
        self._credits: dict = {}
        self._ledger: list = []

    def _append_ledger(self, user_id, delta, kind, ref_id="", balance_after=0):
        self._ledger.append(
            {"user_id": user_id, "delta": delta, "kind": kind,
             "ref_id": ref_id, "balance_after": balance_after}
        )

    def add_credits(self, user_id: str, amount: int):
        with self._lock:
            self._credits[user_id] = self._credits.get(user_id, 0) + amount

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


class TestGiftCard(unittest.TestCase):
    def _card(self, **kwargs):
        defaults = dict(
            card_id="cid1", code="ABCD-1234-EF56",
            purchaser_id="u1", amount=100,
        )
        defaults.update(kwargs)
        return GiftCard(**defaults)

    def test_is_valid_new_card(self):
        self.assertTrue(self._card().is_valid())

    def test_is_valid_redeemed_returns_false(self):
        c = self._card(is_redeemed=True)
        self.assertFalse(c.is_valid())

    def test_is_valid_expired_returns_false(self):
        past = datetime.now(timezone.utc) - timedelta(days=1)
        c = self._card(expires_at=past)
        self.assertFalse(c.is_valid())

    def test_is_valid_future_expiry(self):
        future = datetime.now(timezone.utc) + timedelta(days=30)
        c = self._card(expires_at=future)
        self.assertTrue(c.is_valid())

    def test_is_valid_naive_future_expiry_no_typeerror(self):
        # A naive (tz-less) expiry must not raise TypeError when compared to an
        # aware now(); it is treated as UTC. Regression for the promo-code-style
        # naive/aware comparison bug.
        future_naive = datetime.now() + timedelta(days=30)  # noqa: DTZ005 - intentional naive
        c = self._card(expires_at=future_naive)
        self.assertTrue(c.is_valid())

    def test_is_valid_naive_past_expiry_returns_false(self):
        past_naive = datetime.now() - timedelta(days=1)  # noqa: DTZ005 - intentional naive
        c = self._card(expires_at=past_naive)
        self.assertFalse(c.is_valid())

    def test_to_dict_keys(self):
        d = self._card().to_dict()
        for key in ("card_id", "code", "purchaser_id", "amount", "is_redeemed",
                    "redeemed_by", "message", "expires_at", "is_valid",
                    "created_at", "redeemed_at"):
            self.assertIn(key, d)

    def test_to_public_dict_omits_purchaser_id(self):
        d = self._card().to_public_dict()
        self.assertNotIn("purchaser_id", d)
        self.assertIn("amount", d)

    def test_to_dict_is_valid_reflects_state(self):
        c = self._card(is_redeemed=True)
        self.assertFalse(c.to_dict()["is_valid"])


class TestGiftCardStore(unittest.TestCase):
    def setUp(self):
        self.store = _make_store()

    def test_create_returns_gift_card(self):
        card = self.store.create("u1", 500)
        self.assertEqual(card.purchaser_id, "u1")
        self.assertEqual(card.amount, 500)
        self.assertFalse(card.is_redeemed)

    def test_create_amount_zero_raises(self):
        with self.assertRaises(ValueError):
            self.store.create("u1", 0)

    def test_create_amount_negative_raises(self):
        with self.assertRaises(ValueError):
            self.store.create("u1", -10)

    def test_create_amount_over_max_raises(self):
        with self.assertRaises(ValueError):
            self.store.create("u1", _MAX_AMOUNT + 1)

    def test_create_amount_max_ok(self):
        card = self.store.create("u1", _MAX_AMOUNT)
        self.assertEqual(card.amount, _MAX_AMOUNT)

    def test_code_format(self):
        card = self.store.create("u1", 100)
        parts = card.code.split("-")
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(len(p) == 4 for p in parts))

    def test_get_by_code(self):
        card = self.store.create("u1", 100)
        found = self.store.get_by_code(card.code)
        self.assertIsNotNone(found)
        self.assertEqual(found.card_id, card.card_id)

    def test_get_by_code_case_insensitive(self):
        card = self.store.create("u1", 100)
        found = self.store.get_by_code(card.code.lower())
        self.assertIsNotNone(found)

    def test_get_by_code_unknown_returns_none(self):
        self.assertIsNone(self.store.get_by_code("XXXX-XXXX-XXXX"))

    def test_get_by_id(self):
        card = self.store.create("u1", 100)
        found = self.store.get_by_id(card.card_id)
        self.assertIsNotNone(found)

    def test_get_by_id_unknown_returns_none(self):
        self.assertIsNone(self.store.get_by_id("nope"))

    def test_redeem_marks_redeemed(self):
        card = self.store.create("u1", 100)
        redeemed = self.store.redeem(card.code, "u2")
        self.assertTrue(redeemed.is_redeemed)
        self.assertEqual(redeemed.redeemed_by, "u2")
        self.assertIsNotNone(redeemed.redeemed_at)

    def test_redeem_self_raises(self):
        card = self.store.create("u1", 100)
        with self.assertRaises(ValueError):
            self.store.redeem(card.code, "u1")

    def test_redeem_twice_raises(self):
        card = self.store.create("u1", 100)
        self.store.redeem(card.code, "u2")
        with self.assertRaises(ValueError):
            self.store.redeem(card.code, "u3")

    def test_redeem_expired_raises(self):
        past = datetime.now(timezone.utc) - timedelta(days=1)
        card = self.store.create("u1", 100, expires_at=past)
        with self.assertRaises(ValueError):
            self.store.redeem(card.code, "u2")

    def test_create_normalizes_naive_expiry_and_redeem_works(self):
        # A naive future expiry passed to create() must be stored as aware so
        # redeem() (which compares against aware now()) doesn't raise TypeError.
        future_naive = datetime.now() + timedelta(days=30)  # noqa: DTZ005 - intentional naive
        card = self.store.create("u1", 100, expires_at=future_naive)
        self.assertIsNotNone(card.expires_at.tzinfo)
        redeemed = self.store.redeem(card.code, "u2")
        self.assertTrue(redeemed.is_redeemed)

    def test_redeem_unknown_code_raises(self):
        with self.assertRaises(ValueError):
            self.store.redeem("ZZZZ-ZZZZ-ZZZZ", "u2")

    def test_get_my_cards_pagination(self):
        for i in range(5):
            self.store.create("u1", 10 * (i + 1))
        result = self.store.get_my_cards("u1", limit=3, offset=0)
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["items"]), 3)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 3)

    def test_get_my_cards_empty(self):
        result = self.store.get_my_cards("nobody")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])

    def test_message_stored_and_truncated(self):
        long_msg = "x" * 600
        card = self.store.create("u1", 100, message=long_msg)
        self.assertEqual(len(card.message), 500)

    def test_max_vouchers_per_user(self):
        for _ in range(_MAX_VOUCHERS_PER_USER):
            self.store.create("u_heavy", 1)
        with self.assertRaises(ValueError):
            self.store.create("u_heavy", 1)


class TestGiftCardManager(unittest.TestCase):
    def setUp(self):
        self.mkt = _FakeMarketplace()
        self.mkt._credits["buyer"] = 1000
        self.mgr = GiftCardManager()

    def test_purchase_creates_card_and_deducts_credits(self):
        result = self.mgr.purchase("buyer", 200, self.mkt)
        self.assertEqual(self.mkt._credits["buyer"], 800)
        self.assertEqual(result["amount"], 200)
        self.assertIn("code", result)

    def test_purchase_insufficient_credits_raises(self):
        self.mkt._credits["buyer"] = 50
        with self.assertRaises(ValueError):
            self.mgr.purchase("buyer", 100, self.mkt)

    def test_purchase_records_ledger_entry(self):
        self.mgr.purchase("buyer", 100, self.mkt)
        entry = next(e for e in self.mkt._ledger if e["kind"] == "gift_card_purchase")
        self.assertEqual(entry["delta"], -100)

    def test_purchase_over_max_does_not_debit(self):
        # Regression: an invalid (over-cap) amount must never burn credits.
        self.mkt._credits["buyer"] = 1000
        with self.assertRaises(ValueError):
            self.mgr.purchase("buyer", _MAX_AMOUNT + 1, self.mkt)
        self.assertEqual(self.mkt._credits["buyer"], 1000)

    def test_purchase_with_message(self):
        result = self.mgr.purchase("buyer", 100, self.mkt, message="Happy Birthday!")
        self.assertEqual(result["message"], "Happy Birthday!")

    def test_redeem_adds_credits_and_marks_redeemed(self):
        purchase = self.mgr.purchase("buyer", 300, self.mkt)
        code = purchase["code"]
        self.mkt._credits["recipient"] = 0
        result = self.mgr.redeem(code, "recipient", self.mkt)
        self.assertEqual(result["credits_received"], 300)
        self.assertEqual(result["new_balance"], 300)
        self.assertTrue(result["card"]["is_redeemed"])

    def test_redeem_records_ledger_entry(self):
        purchase = self.mgr.purchase("buyer", 100, self.mkt)
        code = purchase["code"]
        self.mkt._credits["recipient"] = 0
        self.mgr.redeem(code, "recipient", self.mkt)
        entry = next(e for e in self.mkt._ledger if e["kind"] == "gift_card_redeem")
        self.assertEqual(entry["delta"], 100)

    def test_redeem_self_raises(self):
        purchase = self.mgr.purchase("buyer", 100, self.mkt)
        with self.assertRaises(ValueError):
            self.mgr.redeem(purchase["code"], "buyer", self.mkt)

    def test_redeem_omits_purchaser_id_from_response(self):
        purchase = self.mgr.purchase("buyer", 100, self.mkt)
        self.mkt._credits["recipient"] = 0
        result = self.mgr.redeem(purchase["code"], "recipient", self.mkt)
        self.assertNotIn("purchaser_id", result["card"])

    def test_lookup_returns_amount_and_validity(self):
        purchase = self.mgr.purchase("buyer", 250, self.mkt)
        info = self.mgr.lookup(purchase["code"])
        self.assertIsNotNone(info)
        self.assertEqual(info["amount"], 250)
        self.assertTrue(info["is_valid"])
        self.assertFalse(info["is_redeemed"])

    def test_lookup_no_purchaser_id(self):
        purchase = self.mgr.purchase("buyer", 100, self.mkt)
        info = self.mgr.lookup(purchase["code"])
        self.assertNotIn("purchaser_id", info)

    def test_lookup_unknown_returns_none(self):
        self.assertIsNone(self.mgr.lookup("DEAD-DEAD-DEAD"))

    def test_get_my_cards_returns_paginated(self):
        for _ in range(3):
            self.mgr.purchase("buyer", 50, self.mkt)
        result = self.mgr.get_my_cards("buyer")
        self.assertEqual(result["total"], 3)
        self.assertEqual(len(result["items"]), 3)

    def test_purchase_with_expiry(self):
        future = datetime.now(timezone.utc) + timedelta(days=7)
        result = self.mgr.purchase("buyer", 100, self.mkt, expires_at=future)
        self.assertIsNotNone(result["expires_at"])

    def test_redeem_rolls_back_on_credit_failure(self):
        """Card must not be permanently consumed if credit delivery fails."""
        purchase = self.mgr.purchase("buyer", 100, self.mkt)
        code = purchase["code"]

        class _BrokenMarketplace(_FakeMarketplace):
            def credit(self, *args, **kwargs):
                raise RuntimeError("payment service unavailable")

        broken_mkt = _BrokenMarketplace()
        with self.assertRaises(RuntimeError):
            self.mgr.redeem(code, "recipient", broken_mkt)

        # Card must be available for a retry — not burned
        info = self.mgr.lookup(code)
        self.assertIsNotNone(info)
        self.assertTrue(info["is_valid"])
        self.assertFalse(info["is_redeemed"])

    def test_reverse_redemption_restores_card_state(self):
        """_reverse_redemption() on an un-redeemed card is a safe no-op."""
        store = GiftCardStore()
        card = store.create("u1", 50)
        # Simulate a successful redemption then rollback
        store.redeem(card.code, "u2")
        self.assertTrue(store.get_by_id(card.card_id).is_redeemed)
        store._reverse_redemption(card.card_id)
        restored = store.get_by_id(card.card_id)
        self.assertFalse(restored.is_redeemed)
        self.assertEqual(restored.redeemed_by, "")
        self.assertIsNone(restored.redeemed_at)


class TestGiftCardSingleton(unittest.TestCase):
    def test_singleton_same_instance(self):
        a = get_gift_card_manager()
        b = get_gift_card_manager()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
