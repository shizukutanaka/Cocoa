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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
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
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True

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
            "published_at": self.published_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Review:
    review_id: str
    listing_id: str
    user_id: str
    username: str
    stars: int
    text: str
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
        self._featured: List[str] = []  # ordered list of featured listing_ids
        self._price_history: Dict[str, List[Dict[str, Any]]] = {}  # listing_id → [{price_credits, is_free, changed_at}]
        self._disputes: Dict[str, PurchaseDispute] = {}  # dispute_id → PurchaseDispute
        self._lock = threading.Lock()

    # --- Credits ledger ---

    def get_balance(self, user_id: str) -> int:
        with self._lock:
            return self._credits.get(user_id, 0)

    def add_credits(self, user_id: str, amount: int) -> int:
        """Add credits to a user's balance (admin grant or purchase). Returns new balance."""
        if amount <= 0:
            raise ValueError("amount must be positive")
        with self._lock:
            self._credits[user_id] = self._credits.get(user_id, 0) + amount
            return self._credits[user_id]

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
            return {
                "sender_balance": self._credits.get(sender_id, 0),
                "recipient_balance": self._credits[recipient_id],
            }

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

    def download(self, listing_id: str, downloader_id: str) -> Optional[Dict[str, Any]]:
        """Increment download counter and return the avatar parameters for cloning.

        Raises ValueError if the listing is not free and the downloader has insufficient credits.
        The owner downloading their own listing is always free.
        """
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_active:
                return None
            if not listing.is_free and listing.owner_id != downloader_id:
                self._deduct_credits(downloader_id, listing.price_credits)
            now = datetime.now(timezone.utc)
            listing.download_count += 1
            listing.updated_at = now
            self._download_log.append((listing_id, downloader_id, now))
            return {
                "source_listing_id": listing_id,
                "source_avatar_id": listing.avatar_id,
                "name": f"{listing.name} (copy)",
                "parameters": dict(listing.parameters),
                "tags": list(listing.tags),
                "category": listing.category,
                "thumbnail_url": listing.thumbnail_url,
            }

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

    def get_reviews(self, listing_id: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """Return paginated reviews for a listing, newest first."""
        listing = self._listings.get(listing_id)
        if not listing:
            return {"total": 0, "items": []}
        with self._lock:
            items = sorted(self._reviews[listing_id].values(), key=lambda r: r.created_at, reverse=True)
        total = len(items)
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

    # --- Queries ---

    def search(
        self,
        query: str = "",
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        sort_by: str = "newest",   # newest | downloads | rating
        limit: int = 20,
        offset: int = 0,
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

        # Sort
        if sort_by == "downloads":
            results.sort(key=lambda x: x.download_count, reverse=True)
        elif sort_by == "rating":
            results.sort(key=lambda x: (x.average_rating, x.rating_count), reverse=True)
        else:  # newest
            results.sort(key=lambda x: x.published_at, reverse=True)

        total = len(results)
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
                self._credits[dispute.buyer_id] = (
                    self._credits.get(dispute.buyer_id, 0) + dispute.amount_credits
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
        page = items[offset: offset + limit]
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < total,
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

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            active = [lst for lst in self._listings.values() if lst.is_active]
        return {
            "total_listings": len(active),
            "total_downloads": sum(lst.download_count for lst in active),
            "total_ratings": sum(lst.rating_count for lst in active),
            "categories": list({lst.category for lst in active}),
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


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_marketplace: Optional[MarketplaceStore] = None


def get_marketplace() -> MarketplaceStore:
    global _marketplace
    if _marketplace is None:
        _marketplace = MarketplaceStore()
    return _marketplace
