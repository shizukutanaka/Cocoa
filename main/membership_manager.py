"""Customer membership / loyalty tier system for Cocoa.

Users accumulate lifetime_credits (total credits ever spent on purchases)
and are automatically promoted through tiers.  Tiers grant perks such as
reduced platform fees and a priority badge in search results.

Tiers (lowest → highest):
  bronze  → 0      lifetime credits
  silver  → 1 000
  gold    → 5 000
  diamond → 20 000

Rules:
  - Tier is computed on-the-fly from lifetime_credits (no manual setting)
  - Platform fee discount is applied to marketplace sale proceeds (future integration)
  - Admins may adjust lifetime_credits directly (e.g. retroactive corrections)
  - Thread-safe; all writes are under a per-user lock
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Tier definitions: (name, minimum_lifetime_credits, fee_discount_percent, label)
TIERS: List[Tuple[str, int, int, str]] = [
    ("diamond", 20_000, 15, "Diamond"),
    ("gold",     5_000, 10, "Gold"),
    ("silver",   1_000,  5, "Silver"),
    ("bronze",       0,  0, "Bronze"),
]


def _compute_tier(lifetime_credits: int) -> Tuple[str, int, int, str]:
    """Return (tier_name, threshold, fee_discount_percent, label)."""
    for tier in TIERS:
        if lifetime_credits >= tier[1]:
            return tier
    return TIERS[-1]


@dataclass
class MembershipRecord:
    user_id: str
    lifetime_credits: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def tier(self) -> str:
        return _compute_tier(self.lifetime_credits)[0]

    @property
    def tier_label(self) -> str:
        return _compute_tier(self.lifetime_credits)[3]

    @property
    def fee_discount_percent(self) -> int:
        return _compute_tier(self.lifetime_credits)[2]

    @property
    def next_tier_threshold(self) -> Optional[int]:
        """Credits needed to reach the next tier, or None if already highest."""
        current_threshold = _compute_tier(self.lifetime_credits)[1]
        higher = [t[1] for t in TIERS if t[1] > current_threshold]
        return min(higher) if higher else None

    @property
    def credits_to_next_tier(self) -> Optional[int]:
        nxt = self.next_tier_threshold
        if nxt is None:
            return None
        return max(0, nxt - self.lifetime_credits)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "lifetime_credits": self.lifetime_credits,
            "tier": self.tier,
            "tier_label": self.tier_label,
            "fee_discount_percent": self.fee_discount_percent,
            "next_tier_threshold": self.next_tier_threshold,
            "credits_to_next_tier": self.credits_to_next_tier,
            "updated_at": self.updated_at.isoformat(),
        }


class MembershipStore:
    """Thread-safe in-memory membership store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: Dict[str, MembershipRecord] = {}

    def get_or_create(self, user_id: str) -> MembershipRecord:
        with self._lock:
            if user_id not in self._records:
                self._records[user_id] = MembershipRecord(user_id=user_id)
            return self._records[user_id]

    def add_credits(self, user_id: str, amount: int) -> MembershipRecord:
        """Increase lifetime_credits by amount (must be positive)."""
        if amount <= 0:
            raise ValueError("クレジット追加量は正の整数でなければなりません")
        with self._lock:
            rec = self._records.setdefault(user_id, MembershipRecord(user_id=user_id))
            old_tier = rec.tier
            rec.lifetime_credits += amount
            rec.updated_at = datetime.now(timezone.utc)
            if rec.tier != old_tier:
                logger.info(
                    "Tier upgrade: user=%s %s → %s (lifetime=%d)",
                    user_id, old_tier, rec.tier, rec.lifetime_credits,
                )
            return rec

    def adjust_credits(self, user_id: str, new_lifetime: int) -> MembershipRecord:
        """Admin: set lifetime_credits to an exact value (non-negative)."""
        if new_lifetime < 0:
            raise ValueError("ライフタイムクレジットは0以上でなければなりません")
        with self._lock:
            rec = self._records.setdefault(user_id, MembershipRecord(user_id=user_id))
            rec.lifetime_credits = new_lifetime
            rec.updated_at = datetime.now(timezone.utc)
            return rec

    def list_by_tier(
        self,
        tier: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        with self._lock:
            records = list(self._records.values())
        if tier:
            records = [r for r in records if r.tier == tier]
        records.sort(key=lambda r: r.lifetime_credits, reverse=True)
        total = len(records)
        page = records[offset: offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [r.to_dict() for r in page],
        }

    def get_tier_distribution(self) -> Dict[str, int]:
        with self._lock:
            records = list(self._records.values())
        dist: Dict[str, int] = {t[0]: 0 for t in TIERS}
        for r in records:
            dist[r.tier] = dist.get(r.tier, 0) + 1
        return dist


class MembershipManager:
    """Business logic for the membership/loyalty system."""

    def __init__(self, store: Optional[MembershipStore] = None) -> None:
        self.store = store or MembershipStore()

    def get_membership(self, user_id: str) -> Dict[str, Any]:
        return self.store.get_or_create(user_id).to_dict()

    def record_purchase(self, user_id: str, amount: int) -> Dict[str, Any]:
        """Called after a successful purchase; returns updated membership."""
        if amount <= 0:
            raise ValueError("購入金額は正の整数でなければなりません")
        rec = self.store.add_credits(user_id, amount)
        return rec.to_dict()

    def get_fee_discount(self, user_id: str) -> int:
        """Return the platform-fee discount percent for this user's tier."""
        return self.store.get_or_create(user_id).fee_discount_percent

    # Admin operations

    def _require_admin(self, payload: Dict[str, Any]) -> None:
        if payload.get("role") not in ("admin", "moderator"):
            raise PermissionError("管理者権限が必要です")

    def admin_adjust(
        self,
        admin_payload: Dict[str, Any],
        user_id: str,
        new_lifetime: int,
    ) -> Dict[str, Any]:
        """Admin: set a user's lifetime_credits directly."""
        self._require_admin(admin_payload)
        rec = self.store.adjust_credits(user_id, new_lifetime)
        logger.info(
            "Membership adjusted by %s: user=%s lifetime=%d tier=%s",
            admin_payload.get("sub"), user_id, rec.lifetime_credits, rec.tier,
        )
        return rec.to_dict()

    def list_members(
        self,
        admin_payload: Dict[str, Any],
        tier: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        self._require_admin(admin_payload)
        valid_tiers = {t[0] for t in TIERS}
        if tier and tier not in valid_tiers:
            raise ValueError(f"不正なティア: {tier}。有効値: {sorted(valid_tiers)}")
        return self.store.list_by_tier(tier=tier, limit=limit, offset=offset)

    def tier_distribution(self, admin_payload: Dict[str, Any]) -> Dict[str, int]:
        self._require_admin(admin_payload)
        return self.store.get_tier_distribution()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_membership_manager: Optional[MembershipManager] = None
_mm_lock = threading.Lock()


def get_membership_manager() -> MembershipManager:
    global _membership_manager
    if _membership_manager is None:
        with _mm_lock:
            if _membership_manager is None:
                _membership_manager = MembershipManager()
    return _membership_manager
