"""Listing bundle system for Cocoa.

Creators can group multiple of their own listings into a Bundle with a
bundle-level discount.  Buyers can purchase the entire bundle in one step
at a reduced total cost.

Rules:
  - All listings in a bundle must be owned by the same creator.
  - A bundle must contain 2–20 listings.
  - Bundle discount is 0–90 %.
  - Buying a bundle calls marketplace.download() for each listing the buyer
    doesn't already own (existing owners skip the charge for that item).
  - Bundles can be activated/deactivated by the creator.
"""
from __future__ import annotations

import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MIN_LISTINGS = 2
_MAX_LISTINGS = 20
_MAX_BUNDLES_PER_CREATOR = 50
_MAX_NAME_LEN = 100
_MAX_DESCRIPTION_LEN = 1000


@dataclass
class Bundle:
    bundle_id: str
    creator_id: str
    creator_username: str
    name: str
    description: str
    listing_ids: List[str]
    discount_percent: int       # 0–90
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "creator_id": self.creator_id,
            "creator_username": self.creator_username,
            "name": self.name,
            "description": self.description,
            "listing_ids": list(self.listing_ids),
            "listing_count": len(self.listing_ids),
            "discount_percent": self.discount_percent,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class BundleStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bundles: Dict[str, Bundle] = {}              # bundle_id → Bundle
        self._creator_bundles: Dict[str, List[str]] = {}   # creator_id → [bundle_id]

    def create(
        self,
        creator_id: str,
        creator_username: str,
        name: str,
        description: str,
        listing_ids: List[str],
        discount_percent: int,
    ) -> Bundle:
        with self._lock:
            creator_count = len(self._creator_bundles.get(creator_id, []))
            if creator_count >= _MAX_BUNDLES_PER_CREATOR:
                raise ValueError(f"バンドルは最大{_MAX_BUNDLES_PER_CREATOR}件まで作成できます")
            bundle = Bundle(
                bundle_id=secrets.token_hex(8),
                creator_id=creator_id,
                creator_username=creator_username,
                name=name[:_MAX_NAME_LEN].strip(),
                description=description[:_MAX_DESCRIPTION_LEN].strip(),
                listing_ids=list(listing_ids),
                discount_percent=discount_percent,
            )
            self._bundles[bundle.bundle_id] = bundle
            self._creator_bundles.setdefault(creator_id, []).append(bundle.bundle_id)
            return bundle

    def get(self, bundle_id: str) -> Optional[Bundle]:
        with self._lock:
            return self._bundles.get(bundle_id)

    def update(
        self,
        bundle_id: str,
        requester_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        listing_ids: Optional[List[str]] = None,
        discount_percent: Optional[int] = None,
    ) -> Bundle:
        with self._lock:
            bundle = self._bundles.get(bundle_id)
            if not bundle:
                raise ValueError("バンドルが見つかりません")
            if bundle.creator_id != requester_id:
                raise PermissionError("このバンドルの作成者のみが更新できます")
            if name is not None:
                bundle.name = name[:_MAX_NAME_LEN].strip()
            if description is not None:
                bundle.description = description[:_MAX_DESCRIPTION_LEN].strip()
            if listing_ids is not None:
                bundle.listing_ids = list(listing_ids)
            if discount_percent is not None:
                bundle.discount_percent = discount_percent
            bundle.updated_at = datetime.now(timezone.utc)
            return bundle

    def set_active(self, bundle_id: str, requester_id: str, active: bool) -> Bundle:
        with self._lock:
            bundle = self._bundles.get(bundle_id)
            if not bundle:
                raise ValueError("バンドルが見つかりません")
            if bundle.creator_id != requester_id:
                raise PermissionError("このバンドルの作成者のみが操作できます")
            bundle.is_active = active
            bundle.updated_at = datetime.now(timezone.utc)
            return bundle

    def delete(self, bundle_id: str, requester_id: str) -> None:
        with self._lock:
            bundle = self._bundles.get(bundle_id)
            if not bundle:
                raise ValueError("バンドルが見つかりません")
            if bundle.creator_id != requester_id:
                raise PermissionError("このバンドルの作成者のみが削除できます")
            del self._bundles[bundle_id]
            ids = self._creator_bundles.get(requester_id, [])
            if bundle_id in ids:
                ids.remove(bundle_id)

    def list_by_creator(
        self, creator_id: str, include_inactive: bool = False,
        limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        with self._lock:
            ids = list(reversed(self._creator_bundles.get(creator_id, [])))
            bundles = [self._bundles[i] for i in ids if i in self._bundles]
        if not include_inactive:
            bundles = [b for b in bundles if b.is_active]
        total = len(bundles)
        page = bundles[offset: offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [b.to_dict() for b in page],
        }

    def list_active(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        with self._lock:
            bundles = [b for b in self._bundles.values() if b.is_active]
        bundles.sort(key=lambda b: b.created_at, reverse=True)
        total = len(bundles)
        page = bundles[offset: offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [b.to_dict() for b in page],
        }


class BundleManager:
    """Business logic for bundle creation and purchase."""

    def __init__(self, store: Optional[BundleStore] = None) -> None:
        self.store = store or BundleStore()

    def _validate(
        self, listing_ids: List[str], discount_percent: int,
        marketplace_store: Any, creator_id: str
    ) -> List[Any]:
        """Validate listings belong to creator and count/discount are in range.
        Returns resolved listing objects."""
        if not (_MIN_LISTINGS <= len(listing_ids) <= _MAX_LISTINGS):
            raise ValueError(f"バンドルには{_MIN_LISTINGS}〜{_MAX_LISTINGS}件のリスティングが必要です")
        if not (0 <= discount_percent <= 90):
            raise ValueError("割引率は0〜90%の範囲で設定してください")
        if len(set(listing_ids)) != len(listing_ids):
            raise ValueError("バンドルに重複したリスティングが含まれています")

        listings = []
        for lid in listing_ids:
            lst = marketplace_store._listings.get(lid)
            if not lst or not lst.is_active:
                raise ValueError(f"リスティング {lid} が見つかりません")
            if lst.owner_id != creator_id:
                raise PermissionError("バンドルには自分のリスティングのみを含めることができます")
            listings.append(lst)
        return listings

    def create_bundle(
        self,
        creator_id: str,
        creator_username: str,
        name: str,
        description: str,
        listing_ids: List[str],
        discount_percent: int,
        marketplace_store: Any,
    ) -> Dict[str, Any]:
        self._validate(listing_ids, discount_percent, marketplace_store, creator_id)
        bundle = self.store.create(
            creator_id=creator_id,
            creator_username=creator_username,
            name=name,
            description=description,
            listing_ids=listing_ids,
            discount_percent=discount_percent,
        )
        logger.info("Bundle created: %s by %s", bundle.bundle_id, creator_id)
        return bundle.to_dict()

    def update_bundle(
        self,
        bundle_id: str,
        requester_id: str,
        marketplace_store: Any,
        name: Optional[str] = None,
        description: Optional[str] = None,
        listing_ids: Optional[List[str]] = None,
        discount_percent: Optional[int] = None,
    ) -> Dict[str, Any]:
        if listing_ids is not None or discount_percent is not None:
            # Re-validate if content changes
            b = self.store.get(bundle_id)
            if b is None:
                raise ValueError("バンドルが見つかりません")
            new_ids = listing_ids if listing_ids is not None else b.listing_ids
            new_disc = discount_percent if discount_percent is not None else b.discount_percent
            self._validate(new_ids, new_disc, marketplace_store, requester_id)
        bundle = self.store.update(
            bundle_id, requester_id, name=name, description=description,
            listing_ids=listing_ids, discount_percent=discount_percent,
        )
        return bundle.to_dict()

    def deactivate_bundle(self, bundle_id: str, requester_id: str) -> Dict[str, Any]:
        return self.store.set_active(bundle_id, requester_id, False).to_dict()

    def activate_bundle(self, bundle_id: str, requester_id: str) -> Dict[str, Any]:
        return self.store.set_active(bundle_id, requester_id, True).to_dict()

    def delete_bundle(self, bundle_id: str, requester_id: str) -> None:
        self.store.delete(bundle_id, requester_id)

    def get_bundle(self, bundle_id: str) -> Optional[Dict[str, Any]]:
        b = self.store.get(bundle_id)
        return b.to_dict() if b else None

    def purchase_bundle(
        self,
        bundle_id: str,
        buyer_id: str,
        marketplace_store: Any,
    ) -> Dict[str, Any]:
        """Purchase all listings in the bundle at the discounted total.

        For each listing:
          - Already-owned (previously downloaded) items are skipped (no charge).
          - Remaining items are purchased at unit_price × (1 - discount/100).
        Returns a receipt with per-item detail and total charged.
        """
        bundle = self.store.get(bundle_id)
        if not bundle:
            raise ValueError("バンドルが見つかりません")
        if not bundle.is_active:
            raise ValueError("このバンドルは現在利用できません")
        if bundle.creator_id == buyer_id:
            raise ValueError("自分のバンドルは購入できません")

        discount = max(0, min(90, bundle.discount_percent))
        purchased = []
        skipped = []
        total_charged = 0

        # Check already-owned: scan download log
        with marketplace_store._lock:
            downloaded_ids = {lid for lid, did, _ in marketplace_store._download_log if did == buyer_id}

        for listing_id in bundle.listing_ids:
            with marketplace_store._lock:
                lst = marketplace_store._listings.get(listing_id)
            if not lst or not lst.is_active:
                skipped.append({"listing_id": listing_id, "reason": "unavailable"})
                continue

            if listing_id in downloaded_ids:
                skipped.append({"listing_id": listing_id, "reason": "already_owned"})
                continue

            # Apply bundle discount on top of the listing price
            if lst.is_free:
                unit_price = 0
                final_price = 0
            else:
                unit_price = lst.price_credits
                final_price = max(0, int(unit_price * (100 - discount) / 100))

            # Temporarily create a promo to drive the download at the discounted price
            # We do it by calling download() with the adjusted price via direct credit deduction
            # since we can't pass an arbitrary price to download().
            # Instead, we perform the transaction manually within the lock:
            with marketplace_store._lock:
                # Sold-out enforcement (mirror download()): a stock-limited
                # listing that is exhausted must not be oversold via a bundle.
                if lst.stock_remaining is not None and lst.stock_remaining <= 0:
                    skipped.append({"listing_id": listing_id, "reason": "sold_out"})
                    continue
                if final_price > 0:
                    # Check balance
                    balance = marketplace_store._credits.get(buyer_id, 0)
                    if balance < final_price:
                        skipped.append({"listing_id": listing_id, "reason": "insufficient_credits"})
                        continue
                    marketplace_store._credits[buyer_id] = balance - final_price
                    buyer_bal = marketplace_store._credits[buyer_id]
                    marketplace_store._append_ledger(
                        buyer_id, -final_price, "purchase",
                        ref_id=listing_id, balance_after=buyer_bal,
                    )
                    seller_bal = marketplace_store._credits.get(lst.owner_id, 0) + final_price
                    marketplace_store._credits[lst.owner_id] = seller_bal
                    marketplace_store._append_ledger(
                        lst.owner_id, final_price, "sale",
                        ref_id=listing_id, balance_after=seller_bal,
                    )

                now = datetime.now(timezone.utc)
                lst.download_count += 1
                lst.updated_at = now
                if lst.stock_remaining is not None:
                    lst.stock_remaining = max(0, lst.stock_remaining - 1)
                marketplace_store._download_log.append((listing_id, buyer_id, now))

            purchased.append({
                "listing_id": listing_id,
                "name": lst.name,
                "unit_price": unit_price,
                "final_price": final_price,
                "discount_percent": discount,
            })
            total_charged += final_price

        logger.info(
            "Bundle purchase: %s by %s — %d items, %d credits",
            bundle_id, buyer_id, len(purchased), total_charged,
        )
        return {
            "bundle_id": bundle_id,
            "buyer_id": buyer_id,
            "discount_percent": discount,
            "purchased": purchased,
            "skipped": skipped,
            "total_charged": total_charged,
        }

    def list_my_bundles(
        self, creator_id: str, include_inactive: bool = False,
        limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        return self.store.list_by_creator(creator_id, include_inactive, limit, offset)

    def list_active_bundles(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        return self.store.list_active(limit, offset)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_bundle_manager: Optional[BundleManager] = None
_bm_lock = threading.Lock()


def get_bundle_manager() -> BundleManager:
    global _bundle_manager
    if _bundle_manager is None:
        with _bm_lock:
            if _bundle_manager is None:
                _bundle_manager = BundleManager()
    return _bundle_manager
