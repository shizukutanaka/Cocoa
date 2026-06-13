"""
Avatar Marketplace

Features:
- Publish avatars as public (share with the community)
- Browse / search public avatars
- Download (clone) a public avatar to your own collection
- Rating system (1-5 stars, one vote per user)
- Tag-based discovery
- Trending / newest / top-rated feeds
"""
from __future__ import annotations

import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from .pagination import normalize_pagination
except ImportError:  # pragma: no cover - support flat import in tests
    from pagination import normalize_pagination

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class ListingVersion:
    version_id: str
    listing_id: str
    version_number: int     # sequential: 1, 2, 3, …
    name: str
    description: str
    parameters: Dict[str, Any]
    changelog: str          # what changed in this version
    created_by: str         # owner_id
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "listing_id": self.listing_id,
            "version_number": self.version_number,
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "changelog": self.changelog,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class MarketplaceListing:
    listing_id: str
    avatar_id: str
    owner_id: str
    owner_username: str
    name: str
    description: str
    tags: List[str]
    category: str
    parameters: Dict[str, Any]
    thumbnail_url: str
    is_free: bool = True
    price_credits: int = 0
    license_type: str = "personal"  # personal | cc_by | cc_by_sa | commercial | custom
    license_details: str = ""
    download_count: int = 0
    rating_sum: int = 0
    rating_count: int = 0
    current_version: int = 1  # latest version number
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    stock_limit: Optional[int] = None      # None = unlimited copies
    stock_remaining: Optional[int] = None  # decremented on each download

    @property
    def average_rating(self) -> float:
        if self.rating_count == 0:
            return 0.0
        return round(self.rating_sum / self.rating_count, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "avatar_id": self.avatar_id,
            "owner_id": self.owner_id,
            "owner_username": self.owner_username,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "category": self.category,
            "thumbnail_url": self.thumbnail_url,
            "is_free": self.is_free,
            "price_credits": self.price_credits,
            "license_type": self.license_type,
            "license_details": self.license_details,
            "download_count": self.download_count,
            "average_rating": self.average_rating,
            "rating_count": self.rating_count,
            "current_version": self.current_version,
            "published_at": self.published_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "stock_limit": self.stock_limit,
            "stock_remaining": self.stock_remaining,
            "is_sold_out": self.stock_remaining is not None and self.stock_remaining <= 0,
        }


@dataclass
class Review:
    review_id: str
    listing_id: str
    user_id: str
    username: str
    stars: int
    text: str
    helpful_count: int = 0
    unhelpful_count: int = 0
    is_hidden: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "listing_id": self.listing_id,
            "user_id": self.user_id,
            "username": self.username,
            "stars": self.stars,
            "text": self.text,
            "helpful_count": self.helpful_count,
            "unhelpful_count": self.unhelpful_count,
            "is_hidden": self.is_hidden,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class ReviewReply:
    reply_id: str
    review_id: str
    user_id: str
    username: str
    text: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reply_id": self.reply_id,
            "review_id": self.review_id,
            "user_id": self.user_id,
            "username": self.username,
            "text": self.text,
            "created_at": self.created_at.isoformat(),
        }


_REPORT_REASONS = frozenset({
    "inappropriate", "spam", "copyright", "misleading", "malware", "other"
})

_DISPUTE_REASONS = frozenset({
    "not_as_described", "corrupted_file", "duplicate_charge", "unauthorized", "other"
})


@dataclass
class PurchaseDispute:
    dispute_id: str
    listing_id: str
    buyer_id: str
    seller_id: str
    amount_credits: int
    reason: str
    details: str
    status: str = "open"  # open | resolved_refund | resolved_release
    resolved_by: str = ""
    resolution_note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dispute_id": self.dispute_id,
            "listing_id": self.listing_id,
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "amount_credits": self.amount_credits,
            "reason": self.reason,
            "details": self.details,
            "status": self.status,
            "resolved_by": self.resolved_by,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class PromoCode:
    code_id: str
    code: str               # uppercased alphanumeric string
    creator_id: str         # must own the listing (or listing_id=None for any listing by creator)
    discount_percent: int   # 1-99
    listing_id: Optional[str] = None  # None = applies to any of creator's listings
    max_uses: Optional[int] = None    # None = unlimited
    uses_count: int = 0
    expires_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.max_uses is not None and self.uses_count >= self.max_uses:
            return False
        return not (self.expires_at and datetime.now(timezone.utc) > self.expires_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code_id": self.code_id,
            "code": self.code,
            "creator_id": self.creator_id,
            "discount_percent": self.discount_percent,
            "listing_id": self.listing_id,
            "max_uses": self.max_uses,
            "uses_count": self.uses_count,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
            "is_valid": self.is_valid(),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Tip:
    tip_id: str
    sender_id: str
    sender_username: str
    recipient_id: str
    amount: int     # credits transferred
    message: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tip_id": self.tip_id,
            "sender_id": self.sender_id,
            "sender_username": self.sender_username,
            "recipient_id": self.recipient_id,
            "amount": self.amount,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ListingReport:
    report_id: str
    listing_id: str
    reporter_id: str
    reason: str
    details: str
    status: str = "pending"  # pending | resolved | dismissed
    resolved_by: str = ""
    resolution_note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "listing_id": self.listing_id,
            "reporter_id": self.reporter_id,
            "reason": self.reason,
            "details": self.details,
            "status": self.status,
            "resolved_by": self.resolved_by,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class ReviewReport:
    report_id: str
    review_id: str
    reporter_id: str
    reason: str   # spam | offensive | false_info | other
    details: str
    status: str = "pending"  # pending | resolved | dismissed
    resolved_by: str = ""
    resolution_note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "review_id": self.review_id,
            "reporter_id": self.reporter_id,
            "reason": self.reason,
            "details": self.details,
            "status": self.status,
            "resolved_by": self.resolved_by,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


# ---------------------------------------------------------------------------
# In-memory store (production: swap for DB table)
# ---------------------------------------------------------------------------
class MarketplaceStore:
    def __init__(self):
        self._listings: Dict[str, MarketplaceListing] = {}
        self._votes: Dict[str, Dict[str, int]] = {}  # listing_id → {user_id: stars}
        self._reviews: Dict[str, Dict[str, Review]] = {}  # listing_id → {user_id: Review}
        self._download_log: List[Tuple[str, str, datetime]] = []  # (listing_id, downloader_id, ts)
        self._reports: Dict[str, ListingReport] = {}  # report_id → ListingReport
        self._credits: Dict[str, int] = {}  # user_id → credit balance
        self._quotas: Dict[str, int] = {}  # user_id → max active listings (None/missing = unlimited)
        self._review_replies: Dict[str, List[ReviewReply]] = {}  # review_id → [Reply]
        self._review_votes: Dict[str, Dict[str, bool]] = {}  # review_id → {user_id: helpful?}
        self._featured: List[str] = []  # ordered list of featured listing_ids
        self._price_history: Dict[str, List[Dict[str, Any]]] = {}  # listing_id → [{price_credits, is_free, changed_at}]
        self._disputes: Dict[str, PurchaseDispute] = {}  # dispute_id → PurchaseDispute
        self._versions: Dict[str, List[ListingVersion]] = {}  # listing_id → [ListingVersion], oldest first
        self._credit_ledger: Dict[str, List[Dict[str, Any]]] = {}  # user_id → [{amount, kind, ref_id, balance_after, ts}]
        self._review_reports: Dict[str, ReviewReport] = {}  # report_id → ReviewReport
        self._promo_codes: Dict[str, PromoCode] = {}  # code_id → PromoCode
        self._tips: List[Tip] = []  # chronological list of tips
        self._lock = threading.Lock()

    # --- Credits ledger ---

    def get_balance(self, user_id: str) -> int:
        with self._lock:
            return self._credits.get(user_id, 0)

    def _append_ledger(
        self,
        user_id: str,
        amount: int,
        kind: str,
        ref_id: str = "",
        balance_after: int = 0,
    ) -> None:
        """Append one credit ledger entry (must be called while holding self._lock)."""
        entry = {
            "amount": amount,
            "kind": kind,
            "ref_id": ref_id,
            "balance_after": balance_after,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self._credit_ledger.setdefault(user_id, []).append(entry)

    def get_credit_history(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        """Return paginated credit transaction history for a user (newest first)."""
        with self._lock:
            all_entries = list(reversed(self._credit_ledger.get(user_id, [])))
        total = len(all_entries)
        offset, limit = normalize_pagination(offset, limit)
        page = all_entries[offset : offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": page,
        }

    def add_credits(self, user_id: str, amount: int) -> int:
        """Add credits to a user's balance (admin grant or purchase). Returns new balance."""
        if amount <= 0:
            raise ValueError("amount must be positive")
        with self._lock:
            self._credits[user_id] = self._credits.get(user_id, 0) + amount
            bal = self._credits[user_id]
            self._append_ledger(user_id, amount, "grant", balance_after=bal)
            return bal

    def _deduct_credits(self, user_id: str, amount: int) -> None:
        """Deduct credits; raises ValueError if insufficient balance. Call within lock."""
        balance = self._credits.get(user_id, 0)
        if balance < amount:
            raise ValueError(f"残高不足 (残高: {balance}, 必要: {amount})")
        self._credits[user_id] = balance - amount

    def gift_credits(self, sender_id: str, recipient_id: str, amount: int) -> Dict[str, int]:
        """Transfer credits from sender to recipient. Returns new balances for both."""
        if amount <= 0:
            raise ValueError("ギフト額は1以上の整数で指定してください")
        if sender_id == recipient_id:
            raise ValueError("自分自身にギフトすることはできません")
        with self._lock:
            self._deduct_credits(sender_id, amount)
            self._credits[recipient_id] = self._credits.get(recipient_id, 0) + amount
            sender_bal = self._credits.get(sender_id, 0)
            recipient_bal = self._credits[recipient_id]
            self._append_ledger(sender_id, -amount, "gift_sent",
                                 ref_id=recipient_id, balance_after=sender_bal)
            self._append_ledger(recipient_id, amount, "gift_received",
                                 ref_id=sender_id, balance_after=recipient_bal)
            return {
                "sender_balance": sender_bal,
                "recipient_balance": recipient_bal,
            }

    def credit(self, user_id: str, amount: int, kind: str, ref_id: str = "") -> int:
        """Atomically add credits with a custom ledger kind. Returns new balance.

        Public, audited entry point for other subsystems (gift cards, refunds,
        referrals, …) so they need not touch the private balance store directly.
        """
        if amount <= 0:
            raise ValueError("amount must be positive")
        with self._lock:
            new_bal = self._credits.get(user_id, 0) + amount
            self._credits[user_id] = new_bal
            self._append_ledger(user_id, amount, kind, ref_id=ref_id, balance_after=new_bal)
            return new_bal

    def debit(self, user_id: str, amount: int, kind: str, ref_id: str = "") -> int:
        """Atomically deduct credits with a custom ledger kind. Returns new balance.

        Raises ValueError if the balance is insufficient.  Public, audited
        counterpart to ``credit`` for other subsystems.
        """
        if amount <= 0:
            raise ValueError("amount must be positive")
        with self._lock:
            self._deduct_credits(user_id, amount)
            new_bal = self._credits.get(user_id, 0)
            self._append_ledger(user_id, -amount, kind, ref_id=ref_id, balance_after=new_bal)
            return new_bal

    # --- Creator quota ---

    def set_quota(self, user_id: str, max_listings: int) -> None:
        """Set max number of active listings for a user (admin only). 0 = blocked."""
        if max_listings < 0:
            raise ValueError("max_listings must be ≥ 0")
        self._quotas[user_id] = max_listings

    def get_quota(self, user_id: str) -> Optional[int]:
        """Return the quota for a user, or None if unlimited."""
        return self._quotas.get(user_id)

    def get_active_listing_count(self, user_id: str) -> int:
        with self._lock:
            return sum(1 for lst in self._listings.values() if lst.owner_id == user_id and lst.is_active)

    # --- Publish ---

    def publish(
        self,
        avatar_id: str,
        owner_id: str,
        owner_username: str,
        name: str,
        description: str,
        tags: List[str],
        category: str,
        parameters: Dict[str, Any],
        thumbnail_url: str = "",
        is_free: bool = True,
        price_credits: int = 0,
        license_type: str = "personal",
        license_details: str = "",
    ) -> MarketplaceListing:
        with self._lock:
            # Enforce creator quota
            quota = self._quotas.get(owner_id)
            if quota is not None:
                active_count = sum(1 for lst in self._listings.values() if lst.owner_id == owner_id and lst.is_active)
                if active_count >= quota:
                    raise ValueError(f"公開上限 ({quota} 件) に達しています。既存のリスティングを削除してから再試行してください")
            # Prevent duplicate listings for same avatar
            for existing in self._listings.values():
                if existing.avatar_id == avatar_id and existing.owner_id == owner_id and existing.is_active:
                    raise ValueError(f"Avatar {avatar_id} is already listed in the marketplace")

            listing = MarketplaceListing(
                listing_id=secrets.token_hex(12),
                avatar_id=avatar_id,
                owner_id=owner_id,
                owner_username=owner_username,
                name=name,
                description=description,
                tags=[t.lower().strip() for t in tags[:20]],
                category=category,
                parameters=parameters,
                thumbnail_url=thumbnail_url,
                is_free=is_free,
                price_credits=price_credits,
                license_type=license_type,
                license_details=license_details.strip()[:500],
            )
            self._listings[listing.listing_id] = listing
            self._votes[listing.listing_id] = {}
            self._reviews[listing.listing_id] = {}
            # Record initial price
            self._price_history[listing.listing_id] = [{
                "price_credits": price_credits,
                "is_free": is_free,
                "changed_at": listing.published_at.isoformat(),
            }]
            # Record initial version (v1)
            v1 = ListingVersion(
                version_id=secrets.token_hex(8),
                listing_id=listing.listing_id,
                version_number=1,
                name=name,
                description=description,
                parameters=dict(parameters),
                changelog="初回公開",
                created_by=owner_id,
                created_at=listing.published_at,
            )
            self._versions[listing.listing_id] = [v1]
            logger.info("Marketplace listing created: %s by %s", name, owner_username)
            return listing

    # --- Update listing ---

    def update_listing(
        self,
        listing_id: str,
        requester_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        thumbnail_url: Optional[str] = None,
        is_free: Optional[bool] = None,
        price_credits: Optional[int] = None,
        license_type: Optional[str] = None,
        license_details: Optional[str] = None,
    ) -> "MarketplaceListing":
        """Update a published listing. Only the owner may update it."""
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_active:
                raise ValueError("Listing not found or inactive")
            if listing.owner_id != requester_id:
                raise PermissionError("Only the owner can update a listing")
            if name is not None:
                listing.name = name.strip()[:200]
            if description is not None:
                listing.description = description.strip()[:2000]
            if tags is not None:
                listing.tags = [t.lower().strip() for t in tags[:20]]
            if parameters is not None:
                listing.parameters = parameters
            if thumbnail_url is not None:
                listing.thumbnail_url = thumbnail_url.strip()[:500]
            if is_free is not None:
                listing.is_free = is_free
            price_changed = False
            if price_credits is not None:
                if price_credits < 0:
                    raise ValueError("price_credits must be ≥ 0")
                if price_credits != listing.price_credits:
                    price_changed = True
                listing.price_credits = price_credits
            if is_free is not None and is_free != listing.is_free:
                price_changed = True
            if license_type is not None:
                listing.license_type = license_type
            if license_details is not None:
                listing.license_details = license_details.strip()[:500]
            listing.updated_at = datetime.now(timezone.utc)
            if price_changed:
                self._price_history.setdefault(listing.listing_id, []).append({
                    "price_credits": listing.price_credits,
                    "is_free": listing.is_free,
                    "changed_at": listing.updated_at.isoformat(),
                })
            return listing

    # --- Unpublish ---

    def unpublish(self, listing_id: str, requester_id: str) -> bool:
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                return False
            if listing.owner_id != requester_id:
                raise PermissionError("Only the owner can unpublish a listing")
            listing.is_active = False
            return True

    # --- Download / Clone ---

    def download(
        self, listing_id: str, downloader_id: str, promo_code: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Increment download counter and return the avatar parameters for cloning.

        Raises ValueError if the listing is not free and the downloader has insufficient credits.
        The owner downloading their own listing is always free.
        If promo_code is given and valid, a discount is applied to the purchase price.
        """
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_active:
                return None
            # Stock enforcement: owner can always re-download their own listing
            if listing.stock_remaining is not None and listing.stock_remaining <= 0 and listing.owner_id != downloader_id:
                raise ValueError("在庫がありません (sold out)")
            paid = not listing.is_free and listing.owner_id != downloader_id

            actual_price = listing.price_credits
            applied_promo: Optional[PromoCode] = None
            if paid and promo_code:
                pc = self._resolve_promo(promo_code.upper().strip(), listing_id, listing.owner_id)
                if pc:
                    discount = max(0, min(99, pc.discount_percent))
                    actual_price = max(0, int(listing.price_credits * (100 - discount) / 100))
                    applied_promo = pc

            if paid:
                self._deduct_credits(downloader_id, actual_price)
                buyer_bal = self._credits.get(downloader_id, 0)
                self._append_ledger(downloader_id, -actual_price, "purchase",
                                     ref_id=listing_id, balance_after=buyer_bal)
                # Credit seller with discounted amount
                self._credits[listing.owner_id] = (
                    self._credits.get(listing.owner_id, 0) + actual_price
                )
                seller_bal = self._credits[listing.owner_id]
                self._append_ledger(listing.owner_id, actual_price, "sale",
                                     ref_id=listing_id, balance_after=seller_bal)
                if applied_promo:
                    applied_promo.uses_count += 1

            now = datetime.now(timezone.utc)
            listing.download_count += 1
            listing.updated_at = now
            if listing.stock_remaining is not None and listing.owner_id != downloader_id:
                listing.stock_remaining -= 1
                if listing.stock_remaining <= 0:
                    logger.info("Listing sold out: %s", listing_id)
            self._download_log.append((listing_id, downloader_id, now))
            result: Dict[str, Any] = {
                "source_listing_id": listing_id,
                "source_avatar_id": listing.avatar_id,
                "name": f"{listing.name} (copy)",
                "parameters": dict(listing.parameters),
                "tags": list(listing.tags),
                "category": listing.category,
                "thumbnail_url": listing.thumbnail_url,
            }
            if applied_promo:
                result["promo_applied"] = {
                    "code": applied_promo.code,
                    "discount_percent": applied_promo.discount_percent,
                    "original_price": listing.price_credits,
                    "actual_price": actual_price,
                }
            return result

    # --- Rating ---

    def rate(self, listing_id: str, user_id: str, stars: int) -> float:
        if stars < 1 or stars > 5:
            raise ValueError("Rating must be 1–5")
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_active:
                raise ValueError("Listing not found")
            if listing.owner_id == user_id:
                raise ValueError("You cannot rate your own listing")

            prev = self._votes[listing_id].get(user_id)
            if prev is not None:
                listing.rating_sum -= prev
                listing.rating_count -= 1

            self._votes[listing_id][user_id] = stars
            listing.rating_sum += stars
            listing.rating_count += 1
            return listing.average_rating

    def review(self, listing_id: str, user_id: str, username: str, stars: int, text: str) -> Tuple[float, Review]:
        """Submit or update a star rating with an optional text review."""
        if stars < 1 or stars > 5:
            raise ValueError("Rating must be 1–5")
        text = text.strip()[:2000]
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_active:
                raise ValueError("Listing not found")
            if listing.owner_id == user_id:
                raise ValueError("You cannot review your own listing")

            prev_stars = self._votes[listing_id].get(user_id)
            if prev_stars is not None:
                listing.rating_sum -= prev_stars
                listing.rating_count -= 1

            self._votes[listing_id][user_id] = stars
            listing.rating_sum += stars
            listing.rating_count += 1

            existing = self._reviews[listing_id].get(user_id)
            if existing:
                existing.stars = stars
                existing.text = text
                existing.updated_at = datetime.now(timezone.utc)
                rv = existing
            else:
                rv = Review(
                    review_id=secrets.token_hex(10),
                    listing_id=listing_id,
                    user_id=user_id,
                    username=username,
                    stars=stars,
                    text=text,
                )
                self._reviews[listing_id][user_id] = rv
            return listing.average_rating, rv

    def get_reviews(
        self,
        listing_id: str,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "newest",  # newest | helpful | rating_high | rating_low
        include_hidden: bool = False,
    ) -> Dict[str, Any]:
        """Return paginated reviews for a listing."""
        listing = self._listings.get(listing_id)
        if not listing:
            return {"total": 0, "items": []}
        with self._lock:
            items = list(self._reviews[listing_id].values())
        if not include_hidden:
            items = [r for r in items if not r.is_hidden]
        if sort_by == "helpful":
            items.sort(key=lambda r: (r.helpful_count, r.created_at), reverse=True)
        elif sort_by == "rating_high":
            items.sort(key=lambda r: (r.stars, r.created_at), reverse=True)
        elif sort_by == "rating_low":
            items.sort(key=lambda r: r.stars)
        else:  # newest
            items.sort(key=lambda r: r.created_at, reverse=True)
        total = len(items)
        offset, limit = normalize_pagination(offset, limit)
        page = items[offset: offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [r.to_dict() for r in page],
        }

    def delete_review(self, listing_id: str, user_id: str) -> bool:
        """Allow a user to delete their own review (stars are kept)."""
        with self._lock:
            rv = self._reviews.get(listing_id, {}).pop(user_id, None)
        return rv is not None

    # --- Review replies ---

    def _find_review(self, review_id: str) -> Optional[Review]:
        """Return the Review object for a given review_id (O(n) scan)."""
        for rv_map in self._reviews.values():
            for rv in rv_map.values():
                if rv.review_id == review_id:
                    return rv
        return None

    def hide_review(self, review_id: str) -> Review:
        """Hide a review from public view (moderator action)."""
        with self._lock:
            rv = self._find_review(review_id)
            if rv is None:
                raise ValueError("レビューが見つかりません")
            rv.is_hidden = True
        logger.info("Review hidden: %s", review_id)
        return rv

    def unhide_review(self, review_id: str) -> Review:
        """Restore a previously hidden review."""
        with self._lock:
            rv = self._find_review(review_id)
            if rv is None:
                raise ValueError("レビューが見つかりません")
            rv.is_hidden = False
        return rv

    def add_review_reply(
        self, review_id: str, user_id: str, username: str, text: str
    ) -> ReviewReply:
        text = text.strip()[:1000]
        if not text:
            raise ValueError("返信内容を入力してください")
        with self._lock:
            if self._find_review(review_id) is None:
                raise ValueError("レビューが見つかりません")
            reply = ReviewReply(
                reply_id=secrets.token_hex(8),
                review_id=review_id,
                user_id=user_id,
                username=username,
                text=text,
            )
            self._review_replies.setdefault(review_id, []).append(reply)
        return reply

    def get_review_replies(self, review_id: str) -> List[ReviewReply]:
        with self._lock:
            return list(self._review_replies.get(review_id, []))

    def delete_review_reply(self, review_id: str, reply_id: str, requester_id: str) -> bool:
        """Delete a reply if the requester is the reply author."""
        with self._lock:
            replies = self._review_replies.get(review_id, [])
            for i, r in enumerate(replies):
                if r.reply_id == reply_id and r.user_id == requester_id:
                    del replies[i]
                    return True
        return False

    def vote_review_helpful(
        self, review_id: str, user_id: str, helpful: bool
    ) -> Dict[str, Any]:
        """Cast or change a helpfulness vote on a review. Returns updated counts.

        Users cannot vote on their own review. Changing vote is allowed.
        Returns None if review not found.
        """
        with self._lock:
            review = self._find_review(review_id)
            if review is None:
                raise ValueError("レビューが見つかりません")
            if review.user_id == user_id:
                raise ValueError("自分のレビューには投票できません")
            votes = self._review_votes.setdefault(review_id, {})
            previous = votes.get(user_id)
            if previous is not None:
                # Undo previous vote
                if previous:
                    review.helpful_count -= 1
                else:
                    review.unhelpful_count -= 1
            if previous == helpful:
                # Toggling off: remove vote
                del votes[user_id]
            else:
                votes[user_id] = helpful
                if helpful:
                    review.helpful_count += 1
                else:
                    review.unhelpful_count += 1
            return {
                "review_id": review_id,
                "helpful_count": review.helpful_count,
                "unhelpful_count": review.unhelpful_count,
                "user_vote": votes.get(user_id),
            }

    def get_user_listings_page(
        self,
        owner_id: str,
        include_inactive: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Return paginated listings for a creator (newest first)."""
        with self._lock:
            items = [
                lst for lst in self._listings.values()
                if lst.owner_id == owner_id and (include_inactive or lst.is_active)
            ]
        items.sort(key=lambda x: x.published_at, reverse=True)
        total = len(items)
        offset, limit = normalize_pagination(offset, limit)
        page = items[offset : offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [lst.to_dict() for lst in page],
        }

    def get_categories(self) -> List[Dict[str, Any]]:
        """Return all categories that have at least one active listing, with counts."""
        from collections import Counter
        with self._lock:
            counts: Counter = Counter(
                lst.category
                for lst in self._listings.values()
                if lst.is_active
            )
        return [
            {"category": cat, "count": cnt}
            for cat, cnt in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        ]

    def get_leaderboard(
        self,
        by: str = "downloads",   # downloads | rating | listings
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return top creators ranked by total downloads, average rating, or listing count."""
        from collections import defaultdict
        with self._lock:
            active = [lst for lst in self._listings.values() if lst.is_active]

        stats: Dict[str, Any] = defaultdict(lambda: {
            "total_downloads": 0,
            "total_rating_sum": 0,
            "total_rating_count": 0,
            "listing_count": 0,
            "owner_id": "",
            "owner_username": "",
        })
        for lst in active:
            s = stats[lst.owner_id]
            s["owner_id"] = lst.owner_id
            s["owner_username"] = lst.owner_username
            s["total_downloads"] += lst.download_count
            s["total_rating_sum"] += lst.rating_sum
            s["total_rating_count"] += lst.rating_count
            s["listing_count"] += 1

        entries = list(stats.values())
        for s in entries:
            rc = s["total_rating_count"]
            s["average_rating"] = round(s["total_rating_sum"] / rc, 2) if rc else 0.0

        if by == "rating":
            entries.sort(key=lambda x: (x["average_rating"], x["total_rating_count"]), reverse=True)
        elif by == "listings":
            entries.sort(key=lambda x: x["listing_count"], reverse=True)
        else:  # downloads
            entries.sort(key=lambda x: x["total_downloads"], reverse=True)

        return [
            {k: v for k, v in e.items() if k not in ("total_rating_sum",)}
            for e in entries[:limit]
        ]

    # --- Queries ---

    def search(
        self,
        query: str = "",
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        sort_by: str = "newest",   # newest | downloads | rating | price_asc | price_desc
        limit: int = 20,
        offset: int = 0,
        is_free: Optional[bool] = None,         # True = free only, False = paid only
        min_price: Optional[int] = None,        # inclusive minimum price_credits
        max_price: Optional[int] = None,        # inclusive maximum price_credits
        license_type: Optional[str] = None,     # filter by license_type exact match
        owner_id: Optional[str] = None,         # filter by owner
        include_facets: bool = False,            # if True, include category/tag/license breakdowns
    ) -> Dict[str, Any]:
        with self._lock:
            results = [lst for lst in self._listings.values() if lst.is_active]

        if query:
            q = query.lower()
            results = [
                lst for lst in results
                if q in lst.name.lower() or q in lst.description.lower() or q in lst.owner_username.lower()
            ]

        if tags:
            tag_set = {t.lower().strip() for t in tags}
            results = [lst for lst in results if tag_set & set(lst.tags)]

        if category:
            results = [lst for lst in results if lst.category.lower() == category.lower()]

        if owner_id:
            results = [lst for lst in results if lst.owner_id == owner_id]

        if license_type:
            results = [lst for lst in results if lst.license_type == license_type]

        # Price filters
        if is_free is not None:
            results = [lst for lst in results if lst.is_free == is_free]
        if min_price is not None:
            results = [lst for lst in results if lst.price_credits >= min_price]
        if max_price is not None:
            results = [lst for lst in results if lst.price_credits <= max_price]

        # Sort
        if sort_by == "downloads":
            results.sort(key=lambda x: x.download_count, reverse=True)
        elif sort_by == "rating":
            results.sort(key=lambda x: (x.average_rating, x.rating_count), reverse=True)
        elif sort_by == "price_asc":
            results.sort(key=lambda x: x.price_credits)
        elif sort_by == "price_desc":
            results.sort(key=lambda x: x.price_credits, reverse=True)
        else:  # newest
            results.sort(key=lambda x: x.published_at, reverse=True)

        total = len(results)
        offset, limit = normalize_pagination(offset, limit)
        page = results[offset: offset + limit]
        has_more = offset + limit < total
        response: Dict[str, Any] = {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [lst.to_dict() for lst in page],
        }
        if include_facets:
            from collections import Counter
            cat_counts: Counter = Counter(lst.category for lst in results)
            lic_counts: Counter = Counter(lst.license_type for lst in results)
            tag_counts: Counter = Counter(
                tag for lst in results for tag in lst.tags
            )
            response["facets"] = {
                "categories": dict(cat_counts.most_common()),
                "license_types": dict(lic_counts.most_common()),
                "top_tags": dict(tag_counts.most_common(20)),
            }
        return response

    def get_listing(self, listing_id: str) -> Optional[MarketplaceListing]:
        return self._listings.get(listing_id)

    def get_user_listings(self, owner_id: str) -> List[MarketplaceListing]:
        return [lst for lst in self._listings.values() if lst.owner_id == owner_id and lst.is_active]

    def get_trending(self, limit: int = 10, days: int = 7) -> List[Dict[str, Any]]:
        """Top listings by recent downloads (within `days` days), falling back to all-time if none."""
        from collections import Counter
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with self._lock:
            recent_counts: Counter = Counter(
                lid for lid, _, ts in self._download_log if ts >= cutoff
            )
            active = [lst for lst in self._listings.values() if lst.is_active]
        if recent_counts:
            active.sort(key=lambda x: recent_counts.get(x.listing_id, 0), reverse=True)
        else:
            active.sort(key=lambda x: x.download_count, reverse=True)
        return [lst.to_dict() for lst in active[:limit]]

    def get_trending_tags(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Aggregate tag popularity across active listings, weighted by downloads.

        Each tag's score = (# listings using it) + (total downloads of those listings).
        Returns [{tag, listing_count, download_count, score}, ...] descending by score.
        """
        from collections import defaultdict
        with self._lock:
            active = [lst for lst in self._listings.values() if lst.is_active]
        listing_counts: Dict[str, int] = defaultdict(int)
        download_counts: Dict[str, int] = defaultdict(int)
        for lst in active:
            for tag in lst.tags:
                listing_counts[tag] += 1
                download_counts[tag] += lst.download_count
        rows = [
            {
                "tag": tag,
                "listing_count": listing_counts[tag],
                "download_count": download_counts[tag],
                "score": listing_counts[tag] + download_counts[tag],
            }
            for tag in listing_counts
        ]
        rows.sort(key=lambda r: (r["score"], r["listing_count"]), reverse=True)
        return rows[:limit]

    def get_tag_feed(
        self,
        tags: List[str],
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "newest",
    ) -> Dict[str, Any]:
        """Return active listings matching ANY of the given tags, paginated."""
        tag_set = {t.lower().strip() for t in tags if t.strip()}
        if not tag_set:
            return {"total": 0, "offset": offset, "limit": limit,
                    "has_more": False, "next_offset": None, "items": []}
        with self._lock:
            results = [
                lst for lst in self._listings.values()
                if lst.is_active and any(t in tag_set for t in lst.tags)
            ]
        if sort_by == "downloads":
            results.sort(key=lambda x: x.download_count, reverse=True)
        elif sort_by == "rating":
            results.sort(key=lambda x: x.average_rating, reverse=True)
        else:  # newest
            results.sort(key=lambda x: x.published_at, reverse=True)
        total = len(results)
        offset, limit = normalize_pagination(offset, limit)
        page = results[offset: offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [lst.to_dict() for lst in page],
        }

    # --- Featured listings (admin-curated) ---

    def feature_listing(self, listing_id: str) -> bool:
        """Add a listing to the featured list (no-op if already featured)."""
        with self._lock:
            if listing_id in self._listings and listing_id not in self._featured:
                self._featured.append(listing_id)
                return True
        return False

    def unfeature_listing(self, listing_id: str) -> bool:
        """Remove a listing from the featured list."""
        with self._lock:
            try:
                self._featured.remove(listing_id)
                return True
            except ValueError:
                return False

    def get_featured(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return featured active listings in curator order."""
        with self._lock:
            ids = list(self._featured[:limit])
        result = []
        for lid in ids:
            lst = self._listings.get(lid)
            if lst and lst.is_active:
                result.append(lst.to_dict())
        return result

    # --- Price history ---

    def get_price_history(self, listing_id: str) -> List[Dict[str, Any]]:
        """Return the price change log for a listing (oldest first)."""
        with self._lock:
            return list(self._price_history.get(listing_id, []))

    # --- Listing versions ---

    def publish_version(
        self,
        listing_id: str,
        requester_id: str,
        changelog: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> ListingVersion:
        """Create a new version of an existing listing. Only the owner can do this."""
        changelog = changelog.strip()[:1000]
        if not changelog:
            raise ValueError("変更履歴を入力してください")
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_active:
                raise ValueError("リスティングが見つかりません")
            if listing.owner_id != requester_id:
                raise PermissionError("オーナーのみバージョンを更新できます")
            # Update listing fields if provided
            if name is not None:
                listing.name = name.strip()[:200]
            if description is not None:
                listing.description = description.strip()[:2000]
            if parameters is not None:
                listing.parameters = parameters
            listing.current_version += 1
            listing.updated_at = datetime.now(timezone.utc)
            version = ListingVersion(
                version_id=secrets.token_hex(8),
                listing_id=listing_id,
                version_number=listing.current_version,
                name=listing.name,
                description=listing.description,
                parameters=dict(listing.parameters),
                changelog=changelog,
                created_by=requester_id,
            )
            self._versions.setdefault(listing_id, []).append(version)
        logger.info("Version %d published for listing %s", listing.current_version, listing_id)
        return version

    def get_versions(self, listing_id: str) -> List[ListingVersion]:
        """Return all versions for a listing (oldest first)."""
        with self._lock:
            return list(self._versions.get(listing_id, []))

    def get_version(self, listing_id: str, version_number: int) -> Optional[ListingVersion]:
        with self._lock:
            for v in self._versions.get(listing_id, []):
                if v.version_number == version_number:
                    return v
        return None

    # --- Purchase disputes ---

    def open_dispute(
        self,
        listing_id: str,
        buyer_id: str,
        reason: str,
        details: str = "",
    ) -> PurchaseDispute:
        if reason not in _DISPUTE_REASONS:
            raise ValueError(f"Invalid reason. Must be one of: {', '.join(sorted(_DISPUTE_REASONS))}")
        details = details.strip()[:1000]
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                raise ValueError("リスティングが見つかりません")
            if listing.is_free or listing.price_credits == 0:
                raise ValueError("無料リスティングは争議の対象外です")
            # Verify buyer actually downloaded this listing
            downloaded = any(lid == listing_id and did == buyer_id for lid, did, _ in self._download_log)
            if not downloaded:
                raise ValueError("ダウンロード履歴がありません")
            # One open dispute per buyer/listing pair
            for d in self._disputes.values():
                if d.listing_id == listing_id and d.buyer_id == buyer_id and d.status == "open":
                    raise ValueError("既に争議が開いています")
            dispute = PurchaseDispute(
                dispute_id=secrets.token_hex(8),
                listing_id=listing_id,
                buyer_id=buyer_id,
                seller_id=listing.owner_id,
                amount_credits=listing.price_credits,
                reason=reason,
                details=details,
            )
            self._disputes[dispute.dispute_id] = dispute
        logger.info("Dispute opened: %s by buyer %s on listing %s", dispute.dispute_id, buyer_id, listing_id)
        return dispute

    def resolve_dispute(
        self,
        dispute_id: str,
        admin_id: str,
        decision: str,  # "refund" | "release"
        note: str = "",
    ) -> PurchaseDispute:
        if decision not in ("refund", "release"):
            raise ValueError("decision must be 'refund' or 'release'")
        with self._lock:
            dispute = self._disputes.get(dispute_id)
            if not dispute:
                raise ValueError("争議が見つかりません")
            if dispute.status != "open":
                raise ValueError("この争議はすでに解決されています")
            dispute.status = f"resolved_{decision}"
            dispute.resolved_by = admin_id
            dispute.resolution_note = note.strip()[:500]
            dispute.resolved_at = datetime.now(timezone.utc)
            if decision == "refund":
                # Refund the buyer AND claw the proceeds back from the seller so
                # the dispute does not mint credits, recording both sides in the
                # ledger.  The clawback is clamped to the seller's balance (the
                # platform absorbs any shortfall) to keep balances non-negative.
                amount = dispute.amount_credits
                buyer_bal = self._credits.get(dispute.buyer_id, 0) + amount
                self._credits[dispute.buyer_id] = buyer_bal
                self._append_ledger(dispute.buyer_id, amount, "dispute_refund",
                                    ref_id=dispute.listing_id, balance_after=buyer_bal)
                seller_avail = self._credits.get(dispute.seller_id, 0)
                claw = min(seller_avail, amount)
                if claw > 0:
                    seller_bal = seller_avail - claw
                    self._credits[dispute.seller_id] = seller_bal
                    self._append_ledger(dispute.seller_id, -claw, "dispute_reversal",
                                        ref_id=dispute.listing_id, balance_after=seller_bal)
                if claw < amount:
                    logger.warning(
                        "Dispute clawback shortfall: dispute=%s seller=%s owed=%d clawed=%d",
                        dispute_id, dispute.seller_id, amount, claw,
                    )
        logger.info("Dispute %s resolved: %s by admin %s", dispute_id, decision, admin_id)
        return dispute

    def get_disputes(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        with self._lock:
            items = list(self._disputes.values())
        if status:
            items = [d for d in items if d.status == status]
        items.sort(key=lambda d: d.created_at, reverse=True)
        total = len(items)
        offset, limit = normalize_pagination(offset, limit)
        page = items[offset: offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [d.to_dict() for d in page],
        }

    def get_related(self, listing_id: str, limit: int = 6) -> List[Dict[str, Any]]:
        """Return listings similar to the given one, scored by shared tags + same category.

        Scoring: +2 per shared tag, +1 for same category. Excludes the source listing.
        """
        with self._lock:
            source = self._listings.get(listing_id)
            if not source:
                return []
            candidates = [lst for lst in self._listings.values() if lst.is_active and lst.listing_id != listing_id]

        src_tags = set(source.tags)
        src_cat = source.category.lower()
        scored: List[Tuple[float, "MarketplaceListing"]] = []
        for lst in candidates:
            score = 2 * len(src_tags & set(lst.tags))
            if lst.category.lower() == src_cat:
                score += 1
            if score > 0:
                scored.append((score, lst))
        scored.sort(key=lambda x: (-x[0], -x[1].download_count))
        return [lst.to_dict() for _, lst in scored[:limit]]

    def has_downloaded(self, listing_id: str, user_id: str) -> bool:
        """Return True if user_id appears in the download log for listing_id."""
        with self._lock:
            return any(
                lid == listing_id and did == user_id
                for lid, did, _ in self._download_log
            )

    def get_rating_distribution(self, listing_id: str) -> Dict[str, Any]:
        """Return per-star vote counts and average for a listing."""
        with self._lock:
            votes = dict(self._votes.get(listing_id, {}))
        dist: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for stars in votes.values():
            if 1 <= stars <= 5:
                dist[stars] += 1
        total = sum(dist.values())
        avg = round(sum(k * v for k, v in dist.items()) / total, 2) if total else 0.0
        return {
            "listing_id": listing_id,
            "distribution": dist,
            "total_ratings": total,
            "average_rating": avg,
        }

    def clone_listing(
        self, listing_id: str, requester_id: str, requester_username: str
    ) -> "MarketplaceListing":
        """Clone a listing as a new published listing owned by requester.

        Copies all metadata but resets download/rating counters and sets a new owner.
        Useful for remixing a free/open-source avatar.
        """
        with self._lock:
            source = self._listings.get(listing_id)
            if not source or not source.is_active:
                raise ValueError("リスティングが見つかりません")
            if source.license_type not in ("cc_by", "cc_by_sa"):
                raise PermissionError("このライセンスではクローンできません（CC BY または CC BY-SA のみ）")
        # publish uses the lock internally — call outside to avoid deadlock
        cloned = self.publish(
            avatar_id=secrets.token_hex(8),
            owner_id=requester_id,
            owner_username=requester_username,
            name=f"{source.name} (clone)",
            description=source.description,
            tags=list(source.tags),
            category=source.category,
            parameters=dict(source.parameters),
            thumbnail_url=source.thumbnail_url,
            is_free=True,  # clones are always free
            price_credits=0,
            license_type=source.license_type,
            license_details=f"Cloned from listing {listing_id}. {source.license_details}".strip(),
        )
        return cloned

    def transfer_listing(
        self,
        listing_id: str,
        requester_id: str,
        new_owner_id: str,
        new_owner_username: str,
    ) -> "MarketplaceListing":
        """Transfer ownership of a listing to another user.

        Only the current owner may initiate a transfer.
        The listing remains active; all reviews/ratings/downloads are preserved.
        """
        if requester_id == new_owner_id:
            raise ValueError("自分自身に譲渡することはできません")
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                raise ValueError("リスティングが見つかりません")
            if listing.owner_id != requester_id:
                raise PermissionError("このリスティングの所有者のみが譲渡できます")
            listing.owner_id = new_owner_id
            listing.owner_username = new_owner_username
        logger.info("Listing %s transferred from %s to %s", listing_id, requester_id, new_owner_id)
        return listing

    def set_stock_limit(
        self, listing_id: str, owner_id: str, stock_limit: Optional[int]
    ) -> "MarketplaceListing":
        """Set or clear a stock limit for a listing.

        Pass stock_limit=None to make the listing unlimited again.
        Pass a positive integer to cap the number of copies sold.
        Only the listing owner may call this.
        """
        if stock_limit is not None and stock_limit < 0:
            raise ValueError("在庫数は0以上の値を指定してください")
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                raise ValueError("リスティングが見つかりません")
            if listing.owner_id != owner_id:
                raise PermissionError("このリスティングの所有者のみが在庫を設定できます")
            if stock_limit is None:
                listing.stock_limit = None
                listing.stock_remaining = None
            else:
                already_sold = listing.download_count
                remaining = max(0, stock_limit - already_sold)
                listing.stock_limit = stock_limit
                listing.stock_remaining = remaining
            listing.updated_at = datetime.now(timezone.utc)
        logger.info("Stock limit set for listing %s: %s", listing_id, stock_limit)
        return listing

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            active = [lst for lst in self._listings.values() if lst.is_active]
        return {
            "total_listings": len(active),
            "total_downloads": sum(lst.download_count for lst in active),
            "total_ratings": sum(lst.rating_count for lst in active),
            "categories": list({lst.category for lst in active}),
        }

    def get_listing_analytics(self, listing_id: str, owner_id: str) -> Dict[str, Any]:
        """Download/rating analytics for a single listing.

        Only the listing owner may call this (pass owner_id for enforcement).
        Returns download counts by day, reviewer count, and rating breakdown.
        """
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                raise ValueError("リスティングが見つかりません")
            if listing.owner_id != owner_id:
                raise PermissionError("このリスティングの所有者のみが分析情報を取得できます")
            logs = [(lid, did, ts) for lid, did, ts in self._download_log if lid == listing_id]
            review_count = len(self._reviews.get(listing_id, {}))

        from collections import Counter
        day_counts: Counter = Counter()
        unique_downloaders: set = set()
        for _, did, ts in logs:
            day_counts[ts.strftime("%Y-%m-%d")] += 1
            unique_downloaders.add(did)

        dist: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for stars in self._votes.get(listing_id, {}).values():
            if 1 <= stars <= 5:
                dist[stars] += 1
        rating_total = sum(dist.values())
        avg = round(sum(k * v for k, v in dist.items()) / rating_total, 2) if rating_total else 0.0

        return {
            "listing_id": listing_id,
            "name": listing.name,
            "total_downloads": listing.download_count,
            "unique_downloaders": len(unique_downloaders),
            "total_reviews": review_count,
            "average_rating": avg,
            "rating_distribution": dist,
            "downloads_by_day": dict(day_counts),
        }

    def get_creator_analytics(self, owner_id: str) -> Dict[str, Any]:
        """Per-creator dashboard stats."""
        with self._lock:
            listings = [lst for lst in self._listings.values() if lst.owner_id == owner_id]
            logs = [(lid, did, ts) for lid, did, ts in self._download_log
                    if self._listings.get(lid) and self._listings[lid].owner_id == owner_id]

        total_downloads = sum(lst.download_count for lst in listings)
        active_count = sum(1 for lst in listings if lst.is_active)
        total_reviews = sum(len(self._reviews.get(lst.listing_id, {})) for lst in listings)

        # Rating distribution across all listings
        rating_dist: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for lst in listings:
            for stars in self._votes.get(lst.listing_id, {}).values():
                rating_dist[stars] = rating_dist.get(stars, 0) + 1

        # Downloads by day (last 30 days)
        from collections import Counter
        day_counts: Counter = Counter()
        for _, _, ts in logs:
            day_counts[ts.strftime("%Y-%m-%d")] += 1

        # Downloads by tag and category
        listing_map = {lst.listing_id: lst for lst in listings}
        tag_counts: Counter = Counter()
        category_counts: Counter = Counter()
        for lid, _, _ in logs:
            lst = listing_map.get(lid)
            if lst:
                for tag in lst.tags:
                    tag_counts[tag] += 1
                if lst.category:
                    category_counts[lst.category] += 1

        # Revenue (credits earned from paid downloads)
        credits_earned = sum(
            listing_map[lid].price_credits
            for lid, _, _ in logs
            if lid in listing_map and not listing_map[lid].is_free
        )

        # Top listing by downloads
        top = max(listings, key=lambda lst: lst.download_count, default=None)

        return {
            "owner_id": owner_id,
            "total_listings": len(listings),
            "active_listings": active_count,
            "total_downloads": total_downloads,
            "total_reviews": total_reviews,
            "total_credits_earned": credits_earned,
            "rating_distribution": rating_dist,
            "downloads_by_day": dict(day_counts),
            "downloads_by_tag": dict(tag_counts.most_common(20)),
            "downloads_by_category": dict(category_counts),
            "top_listing": top.to_dict() if top else None,
        }

    # --- Earnings summary ---

    def get_earnings_summary(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Aggregate credit earnings from sales and tips for the given window.

        Returns totals by source (sales, tips_received, gifts_received) and a
        day-by-day breakdown for charting.  Uses the credit ledger as the source
        of truth so amounts are always consistent with actual credit movements.
        """
        from collections import defaultdict
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400

        with self._lock:
            entries = list(self._credit_ledger.get(user_id, []))

        total_sales = 0
        total_tips = 0
        by_day: Dict[str, int] = defaultdict(int)

        for entry in entries:
            amount = entry["amount"]
            kind = entry["kind"]
            ts_str = entry.get("ts", "")
            try:
                ts = datetime.fromisoformat(ts_str)
            except (ValueError, TypeError):
                continue
            if ts.timestamp() < cutoff:
                continue

            day = ts.strftime("%Y-%m-%d")
            if kind == "sale" and amount > 0:
                total_sales += amount
                by_day[day] += amount
            elif kind in ("tip_received", "gift_received") and amount > 0:
                total_tips += amount
                by_day[day] += amount

        return {
            "user_id": user_id,
            "period_days": days,
            "total_earned": total_sales + total_tips,
            "sales": total_sales,
            "tips_and_gifts_received": total_tips,
            "by_day": dict(sorted(by_day.items())),
        }

    # --- Download history ---

    def get_user_download_history(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Return paginated list of listings this user has downloaded, newest first."""
        with self._lock:
            entries = [(lid, ts) for lid, did, ts in self._download_log if did == user_id]
        entries.sort(key=lambda x: x[1], reverse=True)
        total = len(entries)
        offset, limit = normalize_pagination(offset, limit)
        page = entries[offset: offset + limit]
        items = []
        for lid, ts in page:
            listing = self._listings.get(lid)
            row: Dict[str, Any] = {"listing_id": lid, "downloaded_at": ts.isoformat()}
            if listing:
                row["name"] = listing.name
                row["owner_username"] = listing.owner_username
                row["is_active"] = listing.is_active
            items.append(row)
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": items,
        }

    # --- Moderation / reports ---

    def report_listing(self, listing_id: str, reporter_id: str, reason: str, details: str = "") -> ListingReport:
        """File a moderation report against a listing."""
        if reason not in _REPORT_REASONS:
            raise ValueError(f"Invalid reason. Must be one of: {', '.join(sorted(_REPORT_REASONS))}")
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                raise ValueError("Listing not found")
            # Prevent duplicate pending reports from same reporter
            for existing in self._reports.values():
                if (existing.listing_id == listing_id and existing.reporter_id == reporter_id
                        and existing.status == "pending"):
                    raise ValueError("You already have a pending report for this listing")
            report = ListingReport(
                report_id=secrets.token_hex(10),
                listing_id=listing_id,
                reporter_id=reporter_id,
                reason=reason,
                details=details.strip()[:1000],
            )
            self._reports[report.report_id] = report
            logger.info("Listing reported: %s (reason=%s)", listing_id, reason)
            return report

    def get_reports(self, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List moderation reports, optionally filtered by status (admin)."""
        with self._lock:
            items = list(self._reports.values())
        if status:
            items = [r for r in items if r.status == status]
        items.sort(key=lambda r: r.created_at, reverse=True)
        total = len(items)
        offset, limit = normalize_pagination(offset, limit)
        page = items[offset: offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [r.to_dict() for r in page],
        }

    def resolve_report(self, report_id: str, moderator_id: str, action: str, note: str = "", *, takedown: bool = False) -> ListingReport:
        """Resolve a report. action: 'resolved' | 'dismissed'. If takedown, unpublish the listing."""
        if action not in ("resolved", "dismissed"):
            raise ValueError("action must be 'resolved' or 'dismissed'")
        with self._lock:
            report = self._reports.get(report_id)
            if not report:
                raise ValueError("Report not found")
            report.status = action
            report.resolved_by = moderator_id
            report.resolution_note = note.strip()[:1000]
            report.resolved_at = datetime.now(timezone.utc)
            if takedown:
                listing = self._listings.get(report.listing_id)
                if listing:
                    listing.is_active = False
                    logger.info("Listing taken down via moderation: %s", report.listing_id)
            return report

    def get_report_stats(self) -> Dict[str, Any]:
        with self._lock:
            items = list(self._reports.values())
        by_status: Dict[str, int] = {"pending": 0, "resolved": 0, "dismissed": 0}
        by_reason: Dict[str, int] = {}
        for r in items:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            by_reason[r.reason] = by_reason.get(r.reason, 0) + 1
        return {"total": len(items), "by_status": by_status, "by_reason": by_reason}

    # --- Review reports ---

    _REVIEW_REPORT_REASONS = frozenset({"spam", "offensive", "false_info", "other"})

    def report_review(
        self, review_id: str, reporter_id: str, reason: str, details: str = ""
    ) -> ReviewReport:
        """File a report against a review. One pending report per user per review."""
        if reason not in self._REVIEW_REPORT_REASONS:
            raise ValueError(f"reason は {sorted(self._REVIEW_REPORT_REASONS)} のいずれかです")
        with self._lock:
            if self._find_review(review_id) is None:
                raise ValueError("レビューが見つかりません")
            for existing in self._review_reports.values():
                if existing.review_id == review_id and existing.reporter_id == reporter_id and existing.status == "pending":
                    raise ValueError("すでにこのレビューへの報告が審査中です")
            report = ReviewReport(
                report_id=secrets.token_hex(10),
                review_id=review_id,
                reporter_id=reporter_id,
                reason=reason,
                details=details.strip()[:1000],
            )
            self._review_reports[report.report_id] = report
        logger.info("Review reported: %s (reason=%s)", review_id, reason)
        return report

    def get_review_reports(
        self, status: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        """List review moderation reports (admin)."""
        with self._lock:
            items = list(self._review_reports.values())
        if status:
            items = [r for r in items if r.status == status]
        items.sort(key=lambda r: r.created_at, reverse=True)
        total = len(items)
        offset, limit = normalize_pagination(offset, limit)
        page = items[offset: offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [r.to_dict() for r in page],
        }

    def resolve_review_report(
        self,
        report_id: str,
        moderator_id: str,
        action: str,  # "resolved" | "dismissed"
        note: str = "",
        *,
        hide: bool = False,
    ) -> ReviewReport:
        """Resolve a review report. If hide=True, hides the review as well."""
        if action not in ("resolved", "dismissed"):
            raise ValueError("action は 'resolved' または 'dismissed' のいずれかです")
        with self._lock:
            report = self._review_reports.get(report_id)
            if not report:
                raise ValueError("報告が見つかりません")
            if report.status != "pending":
                raise ValueError("この報告はすでに処理済みです")
            report.status = action
            report.resolved_by = moderator_id
            report.resolution_note = note.strip()[:1000]
            report.resolved_at = datetime.now(timezone.utc)
            if hide:
                rv = self._find_review(report.review_id)
                if rv:
                    rv.is_hidden = True
        return report

    # --- Promo codes ---

    _MAX_PROMO_CODES_PER_CREATOR = 50

    def _resolve_promo(
        self, code_upper: str, listing_id: str, creator_id: str
    ) -> Optional["PromoCode"]:
        """Return a valid PromoCode for the listing, or None."""
        for pc in self._promo_codes.values():
            if (pc.code == code_upper and pc.creator_id == creator_id and pc.is_valid()
                    and (pc.listing_id is None or pc.listing_id == listing_id)):
                return pc
        return None

    def create_promo_code(
        self,
        creator_id: str,
        code: str,
        discount_percent: int,
        listing_id: Optional[str] = None,
        max_uses: Optional[int] = None,
        expires_at: Optional[datetime] = None,
    ) -> PromoCode:
        """Create a promo code. Only the listing owner may create listing-specific codes."""
        code = code.upper().strip()
        if not code or not code.isalnum():
            raise ValueError("コードは英数字のみ使用できます")
        if len(code) > 32:
            raise ValueError("コードは32文字以内にしてください")
        if not 1 <= discount_percent <= 99:
            raise ValueError("割引率は1〜99の範囲で指定してください")
        if max_uses is not None and max_uses < 1:
            raise ValueError("最大使用回数は1以上にしてください")
        with self._lock:
            if listing_id:
                listing = self._listings.get(listing_id)
                if not listing or not listing.is_active:
                    raise ValueError("リスティングが見つかりません")
                if listing.owner_id != creator_id:
                    raise PermissionError("このリスティングのオーナーのみがプロモコードを作成できます")
            creator_codes = [pc for pc in self._promo_codes.values() if pc.creator_id == creator_id]
            if len(creator_codes) >= self._MAX_PROMO_CODES_PER_CREATOR:
                raise ValueError(f"プロモコードは最大{self._MAX_PROMO_CODES_PER_CREATOR}個まで作成できます")
            # Prevent duplicate active codes for the same creator
            for pc in creator_codes:
                if pc.code == code and pc.is_active:
                    raise ValueError(f"コード '{code}' はすでに存在します")
            promo = PromoCode(
                code_id=secrets.token_hex(8),
                code=code,
                creator_id=creator_id,
                discount_percent=discount_percent,
                listing_id=listing_id,
                max_uses=max_uses,
                expires_at=expires_at,
            )
            self._promo_codes[promo.code_id] = promo
        logger.info("Promo code created: %s by %s", code, creator_id)
        return promo

    def deactivate_promo_code(self, code_id: str, requester_id: str) -> PromoCode:
        """Deactivate a promo code (only the creator can do this)."""
        with self._lock:
            pc = self._promo_codes.get(code_id)
            if not pc:
                raise ValueError("プロモコードが見つかりません")
            if pc.creator_id != requester_id:
                raise PermissionError("このプロモコードのオーナーのみが無効化できます")
            pc.is_active = False
        return pc

    def list_promo_codes(self, creator_id: str) -> List[Dict[str, Any]]:
        """List all promo codes created by a creator."""
        with self._lock:
            codes = [pc for pc in self._promo_codes.values() if pc.creator_id == creator_id]
        codes.sort(key=lambda pc: pc.created_at, reverse=True)
        return [pc.to_dict() for pc in codes]

    def lookup_promo_code(self, code: str, listing_id: str) -> Optional[Dict[str, Any]]:
        """Public lookup: validate a code for a specific listing. Returns info or None."""
        code_upper = code.upper().strip()
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_active:
                return None
            pc = self._resolve_promo(code_upper, listing_id, listing.owner_id)
        if not pc:
            return None
        discount = max(0, min(99, pc.discount_percent))
        discounted = max(0, int(listing.price_credits * (100 - discount) / 100))
        return {
            "code": pc.code,
            "discount_percent": pc.discount_percent,
            "original_price": listing.price_credits,
            "discounted_price": discounted,
            "listing_id": listing_id,
        }

    # --- Tips ---

    _MAX_TIP_AMOUNT = 10_000
    _MAX_TIP_MESSAGE_LEN = 300

    def send_tip(
        self,
        sender_id: str,
        sender_username: str,
        recipient_id: str,
        amount: int,
        message: str = "",
    ) -> Tip:
        """Transfer credits from sender to recipient as a tip with an optional message."""
        if sender_id == recipient_id:
            raise ValueError("自分自身にチップを送ることはできません")
        if amount <= 0:
            raise ValueError("チップは1クレジット以上にしてください")
        if amount > self._MAX_TIP_AMOUNT:
            raise ValueError(f"1回のチップは{self._MAX_TIP_AMOUNT}クレジットまでです")
        message = message.strip()[:self._MAX_TIP_MESSAGE_LEN]
        # Transfer credits (validates sender balance, raises ValueError if insufficient)
        self.gift_credits(sender_id, recipient_id, amount)
        tip = Tip(
            tip_id=secrets.token_hex(8),
            sender_id=sender_id,
            sender_username=sender_username,
            recipient_id=recipient_id,
            amount=amount,
            message=message,
        )
        with self._lock:
            self._tips.append(tip)
        logger.info("Tip sent: %s → %s (%d credits)", sender_id, recipient_id, amount)
        return tip

    def get_tips_received(
        self, recipient_id: str, limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """Return paginated tips received by a user, newest first."""
        with self._lock:
            items = [t for t in self._tips if t.recipient_id == recipient_id]
        items = list(reversed(items))  # newest first
        total = len(items)
        offset, limit = normalize_pagination(offset, limit)
        page = items[offset: offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [t.to_dict() for t in page],
        }

    def get_tips_sent(
        self, sender_id: str, limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """Return paginated tips sent by a user, newest first."""
        with self._lock:
            items = [t for t in self._tips if t.sender_id == sender_id]
        items = list(reversed(items))  # newest first
        total = len(items)
        offset, limit = normalize_pagination(offset, limit)
        page = items[offset: offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [t.to_dict() for t in page],
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_marketplace: Optional[MarketplaceStore] = None


def get_marketplace() -> MarketplaceStore:
    global _marketplace
    if _marketplace is None:
        _marketplace = MarketplaceStore()
    return _marketplace
