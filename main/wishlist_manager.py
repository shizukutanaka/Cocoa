"""Wishlist system for Cocoa avatar marketplace.

Users can wishlist listings they want to buy later.
When a wishlisted listing's price drops, they can be notified.

Features:
  - Add/remove listings from wishlist
  - View own wishlist with listing snapshots
  - Detect price drops for notification (price_drop_check)
  - Max 500 items per wishlist
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from .pagination import normalize_pagination
except ImportError:  # pragma: no cover - support flat import in tests
    from pagination import normalize_pagination

logger = logging.getLogger(__name__)

_MAX_WISHLIST_ITEMS = 500


@dataclass
class WishlistItem:
    listing_id: str
    snapshot_price: int        # price at time of adding
    snapshot_name: str
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "snapshot_price": self.snapshot_price,
            "snapshot_name": self.snapshot_name,
            "added_at": self.added_at.isoformat(),
        }


class WishlistStore:
    """Thread-safe in-memory wishlist store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # user_id → {listing_id: WishlistItem}
        self._wishlists: Dict[str, Dict[str, WishlistItem]] = {}

    def add(self, user_id: str, listing_id: str, snapshot_price: int, snapshot_name: str) -> WishlistItem:
        with self._lock:
            wl = self._wishlists.setdefault(user_id, {})
            if listing_id in wl:
                return wl[listing_id]  # idempotent
            if len(wl) >= _MAX_WISHLIST_ITEMS:
                raise ValueError(f"ウィッシュリストは最大{_MAX_WISHLIST_ITEMS}件までです")
            item = WishlistItem(
                listing_id=listing_id,
                snapshot_price=snapshot_price,
                snapshot_name=snapshot_name,
            )
            wl[listing_id] = item
            return item

    def remove(self, user_id: str, listing_id: str) -> bool:
        with self._lock:
            wl = self._wishlists.get(user_id, {})
            if listing_id in wl:
                del wl[listing_id]
                return True
            return False

    def contains(self, user_id: str, listing_id: str) -> bool:
        with self._lock:
            return listing_id in self._wishlists.get(user_id, {})

    def get_wishlist(self, user_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        with self._lock:
            items = list(self._wishlists.get(user_id, {}).values())
        items.sort(key=lambda x: x.added_at, reverse=True)
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
            "items": [i.to_dict() for i in page],
        }

    def get_wishlisters(self, listing_id: str) -> List[str]:
        """Return user_ids who have this listing wishlisted."""
        with self._lock:
            return [
                uid for uid, wl in self._wishlists.items()
                if listing_id in wl
            ]

    def check_price_drops(self, listing_id: str, current_price: int) -> List[Dict[str, Any]]:
        """Return (user_id, old_price) pairs where current_price < snapshot_price."""
        with self._lock:
            results = []
            for uid, wl in self._wishlists.items():
                item = wl.get(listing_id)
                if item and current_price < item.snapshot_price:
                    results.append({
                        "user_id": uid,
                        "listing_id": listing_id,
                        "old_price": item.snapshot_price,
                        "new_price": current_price,
                    })
            return results

    def clear(self, user_id: str) -> int:
        with self._lock:
            wl = self._wishlists.pop(user_id, {})
            return len(wl)


class WishlistManager:
    """Business logic for wishlist operations."""

    def __init__(self, store: Optional[WishlistStore] = None) -> None:
        self.store = store or WishlistStore()

    def add_item(
        self,
        user_id: str,
        listing_id: str,
        marketplace_store: Any,
    ) -> Dict[str, Any]:
        """Add a listing to the user's wishlist. Returns the wishlist item."""
        with marketplace_store._lock:
            lst = marketplace_store._listings.get(listing_id)
        if not lst or not lst.is_active:
            raise ValueError("リスティングが見つかりません")
        item = self.store.add(user_id, listing_id, lst.price_credits, lst.name)
        return item.to_dict()

    def remove_item(self, user_id: str, listing_id: str) -> bool:
        return self.store.remove(user_id, listing_id)

    def contains(self, user_id: str, listing_id: str) -> bool:
        return self.store.contains(user_id, listing_id)

    def get_wishlist(self, user_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        return self.store.get_wishlist(user_id, limit=limit, offset=offset)

    def get_wishlisters_count(self, listing_id: str) -> int:
        return len(self.store.get_wishlisters(listing_id))

    def check_and_notify_price_drops(
        self,
        listing_id: str,
        current_price: int,
        notification_queue: Any,
    ) -> int:
        """Notify wishlisting users about a price drop. Returns notification count."""
        drops = self.store.check_price_drops(listing_id, current_price)
        count = 0
        for drop in drops:
            try:
                notification_queue.push(
                    drop["user_id"],
                    "price_drop",
                    "ウィッシュリストのアイテムが値下がりしました",
                    f"価格が {drop['old_price']} → {current_price} クレジットに下がりました",
                    payload={
                        "listing_id": listing_id,
                        "old_price": drop["old_price"],
                        "new_price": current_price,
                    },
                )
                count += 1
            except Exception as exc:
                logger.warning("Failed to push price drop notification: %s", exc)
        if count:
            logger.info("Price drop notifications sent for %s: %d users", listing_id, count)
        return count

    def clear_wishlist(self, user_id: str) -> int:
        return self.store.clear(user_id)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_wishlist_manager: Optional[WishlistManager] = None
_wm_lock = threading.Lock()


def get_wishlist_manager() -> WishlistManager:
    global _wishlist_manager
    if _wishlist_manager is None:
        with _wm_lock:
            if _wishlist_manager is None:
                _wishlist_manager = WishlistManager()
    return _wishlist_manager
