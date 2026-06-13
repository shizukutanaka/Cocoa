"""Referral / invite system for Cocoa.

Each registered user gets a unique referral code.  When a new user registers
with that code:
  - A ReferralRecord is created linking referrer ↔ referred.
  - After the referred user completes their first purchase, the referrer
    receives a credit bonus (REFERRAL_BONUS_CREDITS).

Referral state machine:
  pending → converted (first purchase made by referred user)
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

REFERRAL_BONUS_CREDITS = 50   # credits awarded to referrer on conversion
REFERRAL_CODE_LENGTH = 8       # hex chars (e.g. "ab12cd34")


@dataclass
class ReferralRecord:
    referral_id: str
    referrer_id: str
    referred_id: str
    referral_code: str
    status: str = "pending"          # pending | converted
    bonus_awarded: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    converted_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "referral_id": self.referral_id,
            "referrer_id": self.referrer_id,
            "referred_id": self.referred_id,
            "referral_code": self.referral_code,
            "status": self.status,
            "bonus_awarded": self.bonus_awarded,
            "created_at": self.created_at.isoformat(),
            "converted_at": self.converted_at.isoformat() if self.converted_at else None,
        }


class ReferralStore:
    """Thread-safe in-memory referral store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._codes: Dict[str, str] = {}           # code → user_id (owner)
        self._user_code: Dict[str, str] = {}       # user_id → code
        self._records: Dict[str, ReferralRecord] = {}    # referral_id → record
        self._referrer_records: Dict[str, List[str]] = {}  # referrer_id → [referral_id]
        self._referred_by: Dict[str, str] = {}    # referred_id → referral_id

    def get_or_create_code(self, user_id: str) -> str:
        """Return the user's referral code, creating one if it doesn't exist yet."""
        with self._lock:
            if user_id in self._user_code:
                return self._user_code[user_id]
            for _ in range(10):
                code = secrets.token_hex(REFERRAL_CODE_LENGTH // 2).upper()
                if code not in self._codes:
                    self._codes[code] = user_id
                    self._user_code[user_id] = code
                    return code
            raise RuntimeError("Could not generate unique referral code")

    def get_code_owner(self, code: str) -> Optional[str]:
        with self._lock:
            return self._codes.get(code.upper())

    def create_referral(self, referrer_id: str, referred_id: str, code: str) -> ReferralRecord:
        with self._lock:
            if referred_id in self._referred_by:
                raise ValueError("このユーザーはすでに招待コードを使用しています")
            record = ReferralRecord(
                referral_id=secrets.token_hex(8),
                referrer_id=referrer_id,
                referred_id=referred_id,
                referral_code=code.upper(),
            )
            self._records[record.referral_id] = record
            self._referrer_records.setdefault(referrer_id, []).append(record.referral_id)
            self._referred_by[referred_id] = record.referral_id
            return record

    def convert_referral(self, referred_id: str, bonus_credits: int) -> Optional[ReferralRecord]:
        """Mark the referral as converted and record the bonus. Returns None if no referral."""
        with self._lock:
            ref_id = self._referred_by.get(referred_id)
            if not ref_id:
                return None
            record = self._records.get(ref_id)
            if not record or record.status != "pending":
                return None
            record.status = "converted"
            record.bonus_awarded = bonus_credits
            record.converted_at = datetime.now(timezone.utc)
            return record

    def get_referral_by_referred(self, referred_id: str) -> Optional[ReferralRecord]:
        with self._lock:
            ref_id = self._referred_by.get(referred_id)
            return self._records.get(ref_id) if ref_id else None

    def get_referrals_by_referrer(
        self, referrer_id: str, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        with self._lock:
            ids = list(reversed(self._referrer_records.get(referrer_id, [])))
            total = len(ids)
            offset, limit = normalize_pagination(offset, limit)
            page = [self._records[i].to_dict() for i in ids[offset: offset + limit] if i in self._records]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": page,
        }

    def get_referral_stats(self, referrer_id: str) -> Dict[str, Any]:
        with self._lock:
            ids = self._referrer_records.get(referrer_id, [])
            records = [self._records[i] for i in ids if i in self._records]
        total = len(records)
        converted = sum(1 for r in records if r.status == "converted")
        total_bonus = sum(r.bonus_awarded for r in records)
        return {
            "referrer_id": referrer_id,
            "total_referrals": total,
            "converted": converted,
            "pending": total - converted,
            "total_bonus_earned": total_bonus,
        }


class ReferralManager:
    """Business-logic layer for the referral system."""

    def __init__(self, store: Optional[ReferralStore] = None) -> None:
        self.store = store or ReferralStore()

    def get_my_code(self, user_id: str) -> str:
        return self.store.get_or_create_code(user_id)

    def apply_referral_code(
        self, new_user_id: str, code: str
    ) -> Optional[ReferralRecord]:
        """Called at registration time. Returns the created record or None if invalid."""
        code = code.strip().upper()
        if not code:
            return None
        referrer_id = self.store.get_code_owner(code)
        if not referrer_id:
            return None
        if referrer_id == new_user_id:
            raise ValueError("自分の招待コードは使用できません")
        try:
            record = self.store.create_referral(referrer_id, new_user_id, code)
            logger.info("Referral applied: %s → %s", referrer_id, new_user_id)
            return record
        except ValueError:
            return None

    def on_first_purchase(
        self, user_id: str, marketplace_store: Any
    ) -> Optional[ReferralRecord]:
        """Call after a user completes their first purchase.

        If they were referred, awards REFERRAL_BONUS_CREDITS to the referrer,
        marks the referral as converted, and returns the updated record.  The
        bonus is recorded in the ledger with kind "referral_bonus" (not the
        generic "grant") so it is distinguishable in audits, with the referred
        user as ref_id.
        """
        record = self.store.convert_referral(user_id, REFERRAL_BONUS_CREDITS)
        if record is None:
            return None
        try:
            marketplace_store.credit(
                record.referrer_id, REFERRAL_BONUS_CREDITS,
                "referral_bonus", ref_id=user_id,
            )
            logger.info(
                "Referral bonus awarded: %d credits → %s (referred %s)",
                REFERRAL_BONUS_CREDITS, record.referrer_id, user_id,
            )
        except Exception as exc:
            logger.error("Failed to award referral bonus: %s", exc)
        return record

    def get_my_referrals(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        return self.store.get_referrals_by_referrer(user_id, limit=limit, offset=offset)

    def get_my_stats(self, user_id: str) -> Dict[str, Any]:
        return self.store.get_referral_stats(user_id)

    def get_my_referral_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Return how this user was referred (if at all)."""
        record = self.store.get_referral_by_referred(user_id)
        return record.to_dict() if record else None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_referral_manager: Optional[ReferralManager] = None
_rm_lock = threading.Lock()


def get_referral_manager() -> ReferralManager:
    global _referral_manager
    if _referral_manager is None:
        with _rm_lock:
            if _referral_manager is None:
                _referral_manager = ReferralManager()
    return _referral_manager
