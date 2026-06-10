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
    price_credits: int = 0  # future monetisation hook
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


# ---------------------------------------------------------------------------
# In-memory store (production: swap for DB table)
# ---------------------------------------------------------------------------
class MarketplaceStore:
    def __init__(self):
        self._listings: Dict[str, MarketplaceListing] = {}
        self._votes: Dict[str, Dict[str, int]] = {}  # listing_id → {user_id: stars}
        self._reviews: Dict[str, Dict[str, Review]] = {}  # listing_id → {user_id: Review}
        self._download_log: List[Tuple[str, str, datetime]] = []  # (listing_id, downloader_id, ts)
        self._lock = threading.Lock()

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
    ) -> MarketplaceListing:
        with self._lock:
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
            )
            self._listings[listing.listing_id] = listing
            self._votes[listing.listing_id] = {}
            self._reviews[listing.listing_id] = {}
            logger.info("Marketplace listing created: %s by %s", name, owner_username)
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
        """Increment download counter and return the avatar parameters for cloning."""
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_active:
                return None
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
        return {"total": total, "items": [r.to_dict() for r in page]}

    def delete_review(self, listing_id: str, user_id: str) -> bool:
        """Allow a user to delete their own review (stars are kept)."""
        with self._lock:
            rv = self._reviews.get(listing_id, {}).pop(user_id, None)
        return rv is not None

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
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "items": [lst.to_dict() for lst in page],
        }

    def get_listing(self, listing_id: str) -> Optional[MarketplaceListing]:
        return self._listings.get(listing_id)

    def get_user_listings(self, owner_id: str) -> List[MarketplaceListing]:
        return [lst for lst in self._listings.values() if lst.owner_id == owner_id and lst.is_active]

    def get_trending(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Top downloads in the last 7 days — simplified (no time filter in memory store)."""
        with self._lock:
            active = [lst for lst in self._listings.values() if lst.is_active]
        active.sort(key=lambda x: x.download_count, reverse=True)
        return [lst.to_dict() for lst in active[:limit]]

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

        # Top listing by downloads
        top = max(listings, key=lambda lst: lst.download_count, default=None)

        return {
            "owner_id": owner_id,
            "total_listings": len(listings),
            "active_listings": active_count,
            "total_downloads": total_downloads,
            "total_reviews": total_reviews,
            "rating_distribution": rating_dist,
            "downloads_by_day": dict(day_counts),
            "top_listing": top.to_dict() if top else None,
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
