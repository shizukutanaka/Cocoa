"""Shopping cart and order history for the Cocoa avatar marketplace.

Cart lifecycle:
  add_item → remove_item / update_quantity → checkout → Order created

Order states: pending → completed | failed
"""
from __future__ import annotations

import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_CART_ITEMS = 50
_MAX_ORDERS_PER_USER = 1000


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CartItem:
    listing_id: str
    name: str
    owner_id: str
    owner_username: str
    price_credits: int
    is_free: bool
    promo_code: str = ""
    quantity: int = 1
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "name": self.name,
            "owner_id": self.owner_id,
            "owner_username": self.owner_username,
            "price_credits": self.price_credits,
            "is_free": self.is_free,
            "promo_code": self.promo_code,
            "quantity": self.quantity,
            "added_at": self.added_at.isoformat(),
        }


@dataclass
class Cart:
    cart_id: str
    user_id: str
    items: List[CartItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def item_count(self) -> int:
        return sum(i.quantity for i in self.items)

    def subtotal(self) -> int:
        return sum(i.price_credits * i.quantity for i in self.items)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cart_id": self.cart_id,
            "user_id": self.user_id,
            "items": [i.to_dict() for i in self.items],
            "item_count": self.item_count(),
            "subtotal_credits": self.subtotal(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class OrderItem:
    listing_id: str
    name: str
    owner_id: str
    owner_username: str
    unit_price: int
    final_price: int
    quantity: int
    promo_code: str = ""
    discount_percent: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "name": self.name,
            "owner_id": self.owner_id,
            "owner_username": self.owner_username,
            "unit_price": self.unit_price,
            "final_price": self.final_price,
            "quantity": self.quantity,
            "promo_code": self.promo_code,
            "discount_percent": self.discount_percent,
        }


@dataclass
class Order:
    order_id: str
    user_id: str
    items: List[OrderItem]
    total_credits: int
    status: str = "completed"   # completed | failed | refunded
    failure_reason: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "user_id": self.user_id,
            "items": [i.to_dict() for i in self.items],
            "total_credits": self.total_credits,
            "status": self.status,
            "failure_reason": self.failure_reason,
            "item_count": sum(i.quantity for i in self.items),
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class CartStore:
    """Thread-safe in-memory store for carts and orders."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._carts: Dict[str, Cart] = {}       # user_id → Cart
        self._orders: Dict[str, Order] = {}     # order_id → Order
        self._user_orders: Dict[str, List[str]] = {}  # user_id → [order_id, ...]

    # --- Cart operations ---

    def get_cart(self, user_id: str) -> Cart:
        """Return the user's cart, creating one if it doesn't exist."""
        with self._lock:
            if user_id not in self._carts:
                self._carts[user_id] = Cart(
                    cart_id=secrets.token_hex(10),
                    user_id=user_id,
                )
            return self._carts[user_id]

    def add_item(self, user_id: str, item: CartItem) -> Cart:
        """Add a listing to the cart. Duplicate listing_id just updates promo_code."""
        with self._lock:
            cart = self._carts.setdefault(
                user_id,
                Cart(cart_id=secrets.token_hex(10), user_id=user_id),
            )
            # Check for existing item
            existing = next((i for i in cart.items if i.listing_id == item.listing_id), None)
            if existing:
                existing.promo_code = item.promo_code
                existing.price_credits = item.price_credits
            else:
                if len(cart.items) >= _MAX_CART_ITEMS:
                    raise ValueError(f"カートに追加できるアイテムは最大{_MAX_CART_ITEMS}件です")
                cart.items.append(item)
            cart.updated_at = datetime.now(timezone.utc)
            return cart

    def remove_item(self, user_id: str, listing_id: str) -> Cart:
        """Remove a listing from the cart."""
        with self._lock:
            cart = self._carts.get(user_id)
            if not cart:
                raise ValueError("カートが見つかりません")
            cart.items = [i for i in cart.items if i.listing_id != listing_id]
            cart.updated_at = datetime.now(timezone.utc)
            return cart

    def clear_cart(self, user_id: str) -> None:
        with self._lock:
            if user_id in self._carts:
                self._carts[user_id].items = []
                self._carts[user_id].updated_at = datetime.now(timezone.utc)

    def set_promo_code(self, user_id: str, listing_id: str, promo_code: str) -> Cart:
        """Update the promo code for a specific cart item."""
        with self._lock:
            cart = self._carts.get(user_id)
            if not cart:
                raise ValueError("カートが見つかりません")
            item = next((i for i in cart.items if i.listing_id == listing_id), None)
            if not item:
                raise ValueError("カートにそのアイテムが見つかりません")
            item.promo_code = promo_code.strip().upper()
            cart.updated_at = datetime.now(timezone.utc)
            return cart

    # --- Order operations ---

    def create_order(self, user_id: str, items: List[OrderItem], total_credits: int,
                     status: str = "completed", failure_reason: str = "") -> Order:
        with self._lock:
            order = Order(
                order_id=secrets.token_hex(10),
                user_id=user_id,
                items=items,
                total_credits=total_credits,
                status=status,
                failure_reason=failure_reason,
            )
            self._orders[order.order_id] = order
            self._user_orders.setdefault(user_id, []).append(order.order_id)
            # Keep at most _MAX_ORDERS_PER_USER per user
            ids = self._user_orders[user_id]
            if len(ids) > _MAX_ORDERS_PER_USER:
                old_id = ids.pop(0)
                self._orders.pop(old_id, None)
            return order

    def get_order(self, order_id: str) -> Optional[Order]:
        with self._lock:
            return self._orders.get(order_id)

    def get_user_orders(self, user_id: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        with self._lock:
            ids = list(reversed(self._user_orders.get(user_id, [])))
            total = len(ids)
            page_ids = ids[offset: offset + limit]
            items = [self._orders[oid].to_dict() for oid in page_ids if oid in self._orders]
            has_more = offset + limit < total
            return {
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more,
                "next_offset": offset + limit if has_more else None,
                "items": items,
            }


# ---------------------------------------------------------------------------
# Manager (business logic)
# ---------------------------------------------------------------------------

class CartManager:
    """Orchestrates cart operations with marketplace integration."""

    def __init__(self, store: Optional[CartStore] = None) -> None:
        self.store = store or CartStore()

    def get_cart(self, user_id: str) -> Dict[str, Any]:
        return self.store.get_cart(user_id).to_dict()

    def add_item(
        self,
        user_id: str,
        listing_id: str,
        name: str,
        owner_id: str,
        owner_username: str,
        price_credits: int,
        is_free: bool,
        promo_code: str = "",
    ) -> Dict[str, Any]:
        if owner_id == user_id:
            raise ValueError("自分自身のリスティングはカートに追加できません")
        item = CartItem(
            listing_id=listing_id,
            name=name,
            owner_id=owner_id,
            owner_username=owner_username,
            price_credits=price_credits,
            is_free=is_free,
            promo_code=promo_code.strip().upper(),
        )
        cart = self.store.add_item(user_id, item)
        return cart.to_dict()

    def remove_item(self, user_id: str, listing_id: str) -> Dict[str, Any]:
        return self.store.remove_item(user_id, listing_id).to_dict()

    def clear_cart(self, user_id: str) -> None:
        self.store.clear_cart(user_id)

    def set_promo_code(self, user_id: str, listing_id: str, promo_code: str) -> Dict[str, Any]:
        return self.store.set_promo_code(user_id, listing_id, promo_code).to_dict()

    def checkout(self, user_id: str, marketplace_store: Any) -> Dict[str, Any]:
        """Process all items in the cart.

        For each item, calls marketplace_store.download() which handles credit
        deduction and ledger entries atomically.  Returns an Order receipt.

        Raises ValueError if the cart is empty.
        """
        cart = self.store.get_cart(user_id)
        if not cart.items:
            raise ValueError("カートが空です")

        order_items: List[OrderItem] = []
        total_spent = 0
        failed_items: List[Dict[str, Any]] = []

        for item in list(cart.items):
            try:
                result = marketplace_store.download(
                    item.listing_id, user_id, item.promo_code
                )
                if result is None:
                    failed_items.append({"listing_id": item.listing_id, "reason": "リスティングが見つかりません"})
                    continue

                promo_info = result.get("promo_applied")
                final_price = promo_info["actual_price"] if promo_info else (
                    0 if item.is_free else item.price_credits
                )
                discount_pct = promo_info["discount_percent"] if promo_info else 0

                order_items.append(OrderItem(
                    listing_id=item.listing_id,
                    name=item.name,
                    owner_id=item.owner_id,
                    owner_username=item.owner_username,
                    unit_price=item.price_credits,
                    final_price=final_price,
                    quantity=1,
                    promo_code=item.promo_code,
                    discount_percent=discount_pct,
                ))
                total_spent += final_price
            except (ValueError, KeyError) as e:
                failed_items.append({"listing_id": item.listing_id, "reason": str(e)})

        if not order_items and failed_items:
            order = self.store.create_order(
                user_id, [], 0,
                status="failed",
                failure_reason="; ".join(f["reason"] for f in failed_items),
            )
            return {
                "order": order.to_dict(),
                "failed_items": failed_items,
                "success": False,
            }

        order = self.store.create_order(user_id, order_items, total_spent)
        self.store.clear_cart(user_id)
        logger.info("Checkout completed: user=%s order=%s total=%d", user_id, order.order_id, total_spent)
        return {
            "order": order.to_dict(),
            "failed_items": failed_items,
            "success": True,
        }

    def get_order(self, user_id: str, order_id: str) -> Optional[Dict[str, Any]]:
        order = self.store.get_order(order_id)
        if not order or order.user_id != user_id:
            return None
        return order.to_dict()

    def get_orders(self, user_id: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        return self.store.get_user_orders(user_id, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_cart_manager: Optional[CartManager] = None
_cm_lock = threading.Lock()


def get_cart_manager() -> CartManager:
    global _cart_manager
    if _cart_manager is None:
        with _cm_lock:
            if _cart_manager is None:
                _cart_manager = CartManager()
    return _cart_manager
