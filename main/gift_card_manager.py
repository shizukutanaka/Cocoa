"""Gift card / credit voucher system for Cocoa.

Users can purchase gift cards (credit vouchers) and share the code with
others.  The recipient redeems the code to receive the credits.

Rules:
  - Voucher amounts: any positive integer up to MAX_AMOUNT
  - Each code is single-use; redemption deactivates it
  - Purchaser is deducted credits at creation; recipient receives on redeem
  - Optional expiry date
  - Purchaser cannot redeem their own voucher
"""
from __future__ import annotations

import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from .pagination import normalize_pagination
except ImportError:  # pragma: no cover - support flat import in tests
    from pagination import normalize_pagination

logger = logging.getLogger(__name__)

_CODE_BYTES = 6       # 12 uppercase hex chars, grouped as XXXX-XXXX-XXXX
_MAX_AMOUNT = 10_000
_MAX_VOUCHERS_PER_USER = 200


def _generate_code() -> str:
    raw = secrets.token_hex(_CODE_BYTES).upper()
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}"


@dataclass
class GiftCard:
    card_id: str
    code: str
    purchaser_id: str
    amount: int
    is_redeemed: bool = False
    redeemed_by: str = ""
    message: str = ""
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    redeemed_at: Optional[datetime] = None

    def is_valid(self) -> bool:
        if self.is_redeemed:
            return False
        if self.expires_at:
            # Defensive: a naive expiry (e.g. from a direct caller or a
            # deserialized snapshot) would raise TypeError when compared to an
            # aware now().  Normalize to UTC-aware before comparing.
            exp = self.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "card_id": self.card_id,
            "code": self.code,
            "purchaser_id": self.purchaser_id,
            "amount": self.amount,
            "is_redeemed": self.is_redeemed,
            "redeemed_by": self.redeemed_by,
            "message": self.message,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_valid": self.is_valid(),
            "created_at": self.created_at.isoformat(),
            "redeemed_at": self.redeemed_at.isoformat() if self.redeemed_at else None,
        }

    def to_public_dict(self) -> Dict[str, Any]:
        """Omit purchaser_id for privacy when showing to recipient."""
        d = self.to_dict()
        d.pop("purchaser_id", None)
        return d


class GiftCardStore:
    """Thread-safe in-memory gift card store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cards: Dict[str, GiftCard] = {}        # card_id → GiftCard
        self._by_code: Dict[str, str] = {}           # code → card_id
        self._purchaser_cards: Dict[str, List[str]] = {}  # purchaser_id → [card_id]

    def create(
        self,
        purchaser_id: str,
        amount: int,
        message: str = "",
        expires_at: Optional[datetime] = None,
    ) -> GiftCard:
        if amount <= 0 or amount > _MAX_AMOUNT:
            raise ValueError(f"ギフトカードの金額は1〜{_MAX_AMOUNT}クレジットの範囲で設定してください")
        # Normalize a naive expiry to UTC-aware so every stored card compares
        # cleanly against an aware now() at redeem time (mixing naive/aware
        # raises TypeError, which would make the card un-redeemable).
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        with self._lock:
            count = len(self._purchaser_cards.get(purchaser_id, []))
            if count >= _MAX_VOUCHERS_PER_USER:
                raise ValueError(f"ギフトカードは最大{_MAX_VOUCHERS_PER_USER}枚まで作成できます")
            for _ in range(10):
                code = _generate_code()
                if code not in self._by_code:
                    break
            else:
                raise RuntimeError("Failed to generate unique gift card code")

            card = GiftCard(
                card_id=secrets.token_hex(8),
                code=code,
                purchaser_id=purchaser_id,
                amount=amount,
                message=message.strip()[:500],
                expires_at=expires_at,
            )
            self._cards[card.card_id] = card
            self._by_code[code] = card.card_id
            self._purchaser_cards.setdefault(purchaser_id, []).append(card.card_id)
            return card

    def get_by_code(self, code: str) -> Optional[GiftCard]:
        with self._lock:
            cid = self._by_code.get(code.upper().strip())
            return self._cards.get(cid) if cid else None

    def get_by_id(self, card_id: str) -> Optional[GiftCard]:
        with self._lock:
            return self._cards.get(card_id)

    def redeem(self, code: str, redeemer_id: str) -> GiftCard:
        with self._lock:
            cid = self._by_code.get(code.upper().strip())
            card = self._cards.get(cid) if cid else None
            if not card:
                raise ValueError("ギフトカードが見つかりません")
            if card.purchaser_id == redeemer_id:
                raise ValueError("自分で購入したギフトカードは使用できません")
            if card.is_redeemed:
                raise ValueError("このギフトカードはすでに使用済みです")
            if not card.is_valid():
                raise ValueError("このギフトカードの有効期限が切れています")
            card.is_redeemed = True
            card.redeemed_by = redeemer_id
            card.redeemed_at = datetime.now(timezone.utc)
            return card

    def get_my_cards(
        self, purchaser_id: str, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        with self._lock:
            ids = list(reversed(self._purchaser_cards.get(purchaser_id, [])))
            offset, limit = normalize_pagination(offset, limit)
            cards = [self._cards[i].to_dict() for i in ids[offset: offset + limit] if i in self._cards]
            total = len(ids)
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": cards,
        }


class GiftCardManager:
    """Business logic for gift card operations."""

    def __init__(self, store: Optional[GiftCardStore] = None) -> None:
        self.store = store or GiftCardStore()

    def purchase(
        self,
        purchaser_id: str,
        amount: int,
        marketplace_store: Any,
        message: str = "",
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Create a gift card, deducting credits from purchaser."""
        # Validate amount range BEFORE moving any credits, so an invalid
        # request can never debit the purchaser without issuing a card.
        if amount <= 0 or amount > _MAX_AMOUNT:
            raise ValueError(f"ギフトカードの金額は1〜{_MAX_AMOUNT}クレジットの範囲で設定してください")

        # Deduct credits via the marketplace's audited public API
        # (raises ValueError if insufficient balance).
        marketplace_store.debit(purchaser_id, amount, "gift_card_purchase")

        try:
            card = self.store.create(purchaser_id, amount, message, expires_at)
        except Exception:
            # Refund the deducted credits so the purchaser is not charged for a
            # card that was never issued.
            marketplace_store.credit(purchaser_id, amount, "gift_card_purchase_refund")
            raise

        logger.info("Gift card created: %s by %s (%d credits)", card.card_id, purchaser_id, amount)
        return card.to_dict()

    def redeem(
        self,
        code: str,
        redeemer_id: str,
        marketplace_store: Any,
    ) -> Dict[str, Any]:
        """Redeem a gift card code, adding credits to redeemer."""
        card = self.store.redeem(code, redeemer_id)

        new_bal = marketplace_store.credit(
            redeemer_id, card.amount, "gift_card_redeem", ref_id=card.card_id
        )

        logger.info("Gift card redeemed: %s by %s (%d credits)", card.card_id, redeemer_id, card.amount)
        return {
            "card": card.to_public_dict(),
            "credits_received": card.amount,
            "new_balance": new_bal,
        }

    def lookup(self, code: str) -> Optional[Dict[str, Any]]:
        """Public lookup — returns amount/validity without purchaser_id."""
        card = self.store.get_by_code(code)
        if not card:
            return None
        return {
            "amount": card.amount,
            "is_valid": card.is_valid(),
            "is_redeemed": card.is_redeemed,
            "expires_at": card.expires_at.isoformat() if card.expires_at else None,
        }

    def get_my_cards(
        self, purchaser_id: str, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        return self.store.get_my_cards(purchaser_id, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_gift_card_manager: Optional[GiftCardManager] = None
_gc_lock = threading.Lock()


def get_gift_card_manager() -> GiftCardManager:
    global _gift_card_manager
    if _gift_card_manager is None:
        with _gc_lock:
            if _gift_card_manager is None:
                _gift_card_manager = GiftCardManager()
    return _gift_card_manager
