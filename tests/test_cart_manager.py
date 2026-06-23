"""Tests for main/cart_manager.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from cart_manager import (
    Cart,
    CartItem,
    CartManager,
    CartStore,
    Order,
    OrderItem,
    get_cart_manager,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager() -> CartManager:
    return CartManager(CartStore())


def _cart_item(listing_id: str = "lst1", price: int = 100, is_free: bool = False,
               promo: str = "") -> CartItem:
    return CartItem(
        listing_id=listing_id,
        name=f"Avatar {listing_id}",
        owner_id="owner1",
        owner_username="creator",
        price_credits=price,
        is_free=is_free,
        promo_code=promo,
    )


class _FakeListing:
    def __init__(self, listing_id="lst1", owner_id="owner1",
                 price=100, is_free=False, is_active=True):
        self.listing_id = listing_id
        self.owner_id = owner_id
        self.owner_username = "creator"
        self.name = f"Avatar {listing_id}"
        self.price_credits = price
        self.is_free = is_free
        self.is_active = is_active


class _FakeMarketplace:
    """Minimal marketplace stub for checkout tests."""

    def __init__(self):
        self._listings: dict = {}
        self._downloads: list = []

    def add_listing(self, lst: _FakeListing) -> None:
        self._listings[lst.listing_id] = lst

    def download(self, listing_id: str, user_id: str, promo_code: str = ""):
        lst = self._listings.get(listing_id)
        if not lst or not lst.is_active:
            return None
        self._downloads.append((listing_id, user_id))
        amount_paid = 0 if lst.is_free else lst.price_credits
        result: dict = {
            "source_listing_id": listing_id,
            "source_avatar_id": "av1",
            "name": lst.name,
            "parameters": {},
            "tags": [],
            "category": "base",
        }
        if promo_code == "HALF":
            amount_paid = lst.price_credits // 2
            result["promo_applied"] = {
                "code": "HALF",
                "discount_percent": 50,
                "original_price": lst.price_credits,
                "actual_price": lst.price_credits // 2,
            }
        # Mirror the real download() contract: authoritative charged amount.
        result["amount_paid"] = amount_paid
        return result


# ---------------------------------------------------------------------------
# CartItem
# ---------------------------------------------------------------------------

class TestCartItem(unittest.TestCase):
    def test_to_dict_fields(self):
        item = _cart_item("lst1", 200)
        d = item.to_dict()
        self.assertEqual(d["listing_id"], "lst1")
        self.assertEqual(d["price_credits"], 200)
        self.assertIn("added_at", d)

    def test_free_item(self):
        item = _cart_item("lst2", 0, is_free=True)
        d = item.to_dict()
        self.assertTrue(d["is_free"])
        self.assertEqual(d["price_credits"], 0)


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

class TestCart(unittest.TestCase):
    def _make_cart(self) -> Cart:
        c = Cart(cart_id="c1", user_id="u1")
        c.items = [_cart_item("a", 100), _cart_item("b", 200)]
        return c

    def test_item_count(self):
        self.assertEqual(self._make_cart().item_count(), 2)

    def test_subtotal(self):
        self.assertEqual(self._make_cart().subtotal(), 300)

    def test_empty_cart_subtotal(self):
        c = Cart(cart_id="c1", user_id="u1")
        self.assertEqual(c.subtotal(), 0)

    def test_to_dict(self):
        d = self._make_cart().to_dict()
        self.assertIn("cart_id", d)
        self.assertIn("subtotal_credits", d)
        self.assertEqual(d["subtotal_credits"], 300)
        self.assertEqual(len(d["items"]), 2)


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

class TestOrder(unittest.TestCase):
    def _make_order(self) -> Order:
        items = [
            OrderItem("lst1", "Av1", "o1", "cr", 100, 100, 1),
            OrderItem("lst2", "Av2", "o1", "cr", 200, 150, 1, promo_code="SAVE", discount_percent=25),
        ]
        return Order(order_id="ord1", user_id="u1", items=items, total_credits=250)

    def test_to_dict(self):
        d = self._make_order().to_dict()
        self.assertEqual(d["order_id"], "ord1")
        self.assertEqual(d["total_credits"], 250)
        self.assertEqual(d["item_count"], 2)
        self.assertEqual(d["status"], "completed")

    def test_order_item_to_dict(self):
        item = OrderItem("lst1", "Av1", "o1", "cr", 100, 80, 1, "CODE", 20)
        d = item.to_dict()
        self.assertEqual(d["promo_code"], "CODE")
        self.assertEqual(d["discount_percent"], 20)


# ---------------------------------------------------------------------------
# CartStore
# ---------------------------------------------------------------------------

class TestCartStore(unittest.TestCase):
    def setUp(self):
        self.store = CartStore()

    def test_get_cart_creates_new(self):
        cart = self.store.get_cart("user1")
        self.assertEqual(cart.user_id, "user1")
        self.assertEqual(cart.items, [])

    def test_get_cart_returns_same_instance(self):
        c1 = self.store.get_cart("user1")
        c2 = self.store.get_cart("user1")
        self.assertIs(c1, c2)

    def test_add_item_appears_in_cart(self):
        self.store.add_item("u1", _cart_item("lst1"))
        cart = self.store.get_cart("u1")
        self.assertEqual(len(cart.items), 1)
        self.assertEqual(cart.items[0].listing_id, "lst1")

    def test_add_duplicate_updates_promo(self):
        self.store.add_item("u1", _cart_item("lst1", promo="OLD"))
        self.store.add_item("u1", _cart_item("lst1", promo="NEW"))
        cart = self.store.get_cart("u1")
        self.assertEqual(len(cart.items), 1)
        self.assertEqual(cart.items[0].promo_code, "NEW")

    def test_remove_item(self):
        self.store.add_item("u1", _cart_item("lst1"))
        self.store.add_item("u1", _cart_item("lst2"))
        self.store.remove_item("u1", "lst1")
        cart = self.store.get_cart("u1")
        self.assertEqual(len(cart.items), 1)
        self.assertEqual(cart.items[0].listing_id, "lst2")

    def test_remove_item_no_cart_raises(self):
        with self.assertRaises(ValueError):
            self.store.remove_item("no-user", "lst1")

    def test_clear_cart(self):
        self.store.add_item("u1", _cart_item("lst1"))
        self.store.clear_cart("u1")
        self.assertEqual(self.store.get_cart("u1").items, [])

    def test_remove_items_removes_only_listed(self):
        self.store.add_item("u1", _cart_item("lst1"))
        self.store.add_item("u1", _cart_item("lst2"))
        self.store.add_item("u1", _cart_item("lst3"))
        self.store.remove_items("u1", ["lst1", "lst3"])
        remaining = [i.listing_id for i in self.store.get_cart("u1").items]
        self.assertEqual(remaining, ["lst2"])

    def test_remove_items_empty_list_is_noop(self):
        self.store.add_item("u1", _cart_item("lst1"))
        self.store.remove_items("u1", [])
        self.assertEqual(len(self.store.get_cart("u1").items), 1)

    def test_remove_items_unknown_ids_ignored(self):
        self.store.add_item("u1", _cart_item("lst1"))
        self.store.remove_items("u1", ["nope"])
        self.assertEqual(len(self.store.get_cart("u1").items), 1)

    def test_remove_items_no_cart_raises(self):
        with self.assertRaises(ValueError):
            self.store.remove_items("no-user", ["lst1"])

    def test_set_promo_code(self):
        self.store.add_item("u1", _cart_item("lst1"))
        self.store.set_promo_code("u1", "lst1", "SAVE10")
        item = self.store.get_cart("u1").items[0]
        self.assertEqual(item.promo_code, "SAVE10")

    def test_set_promo_no_item_raises(self):
        self.store.get_cart("u1")
        with self.assertRaises(ValueError):
            self.store.set_promo_code("u1", "nonexistent", "CODE")

    def test_set_promo_no_cart_raises(self):
        with self.assertRaises(ValueError):
            self.store.set_promo_code("no-user", "lst1", "CODE")

    def test_create_order(self):
        items = [OrderItem("lst1", "Av", "o1", "cr", 100, 100, 1)]
        order = self.store.create_order("u1", items, 100)
        self.assertEqual(order.user_id, "u1")
        self.assertEqual(order.total_credits, 100)
        self.assertEqual(order.status, "completed")

    def test_get_order_by_id(self):
        items = [OrderItem("lst1", "Av", "o1", "cr", 100, 100, 1)]
        order = self.store.create_order("u1", items, 100)
        fetched = self.store.get_order(order.order_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.order_id, order.order_id)

    def test_get_order_unknown_returns_none(self):
        self.assertIsNone(self.store.get_order("no-such-order"))

    def test_get_user_orders_pagination(self):
        for i in range(5):
            self.store.create_order("u1", [], i * 10)
        result = self.store.get_user_orders("u1", limit=3, offset=0)
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["items"]), 3)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 3)

    def test_get_user_orders_empty(self):
        result = self.store.get_user_orders("no-user")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])


# ---------------------------------------------------------------------------
# CartManager
# ---------------------------------------------------------------------------

class TestCartManagerAddRemove(unittest.TestCase):
    def setUp(self):
        self.mgr = _make_manager()

    def test_add_item_returns_cart(self):
        cart = self.mgr.add_item("u1", "lst1", "Av1", "owner1", "cr", 100, False)
        self.assertIn("items", cart)
        self.assertEqual(len(cart["items"]), 1)

    def test_add_own_listing_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.add_item("u1", "lst1", "Av1", "u1", "cr", 100, False)

    def test_remove_item(self):
        self.mgr.add_item("u1", "lst1", "Av1", "owner1", "cr", 100, False)
        cart = self.mgr.remove_item("u1", "lst1")
        self.assertEqual(cart["items"], [])

    def test_get_cart_initially_empty(self):
        cart = self.mgr.get_cart("new-user")
        self.assertEqual(cart["items"], [])

    def test_clear_cart(self):
        self.mgr.add_item("u1", "lst1", "Av1", "o1", "cr", 50, False)
        self.mgr.clear_cart("u1")
        self.assertEqual(self.mgr.get_cart("u1")["items"], [])

    def test_set_promo_code(self):
        self.mgr.add_item("u1", "lst1", "Av1", "o1", "cr", 100, False)
        cart = self.mgr.set_promo_code("u1", "lst1", "SAVE")
        self.assertEqual(cart["items"][0]["promo_code"], "SAVE")

    def test_promo_code_uppercased(self):
        self.mgr.add_item("u1", "lst1", "Av1", "o1", "cr", 100, False)
        cart = self.mgr.set_promo_code("u1", "lst1", "save10")
        self.assertEqual(cart["items"][0]["promo_code"], "SAVE10")


class TestCartManagerCheckout(unittest.TestCase):
    def setUp(self):
        self.mgr = _make_manager()
        self.mp = _FakeMarketplace()
        self.mp.add_listing(_FakeListing("lst1", "owner1", price=100))
        self.mp.add_listing(_FakeListing("lst2", "owner2", price=200))

    def _add(self, listing_id: str, price: int = 100, owner: str = "owner1",
             promo: str = "") -> None:
        self.mgr.add_item("buyer", listing_id, f"Av{listing_id}", owner, "cr", price, False, promo)

    def test_checkout_creates_order(self):
        self._add("lst1", 100)
        result = self.mgr.checkout("buyer", self.mp)
        self.assertTrue(result["success"])
        order = result["order"]
        self.assertEqual(order["status"], "completed")
        self.assertEqual(len(order["items"]), 1)

    def test_checkout_clears_cart(self):
        self._add("lst1", 100)
        self.mgr.checkout("buyer", self.mp)
        self.assertEqual(self.mgr.get_cart("buyer")["items"], [])

    def test_checkout_empty_cart_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.checkout("buyer", self.mp)

    def test_checkout_multiple_items(self):
        self._add("lst1", 100, "owner1")
        self._add("lst2", 200, "owner2")
        result = self.mgr.checkout("buyer", self.mp)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["order"]["items"]), 2)
        self.assertEqual(result["order"]["total_credits"], 300)

    def test_checkout_with_promo_records_discount(self):
        self._add("lst1", 100, "owner1", "HALF")
        result = self.mgr.checkout("buyer", self.mp)
        item = result["order"]["items"][0]
        self.assertEqual(item["discount_percent"], 50)
        self.assertEqual(item["final_price"], 50)

    def test_checkout_missing_listing_creates_failed_items(self):
        self._add("lst1", 100)
        self._add("nonexistent", 50, "owner1")
        result = self.mgr.checkout("buyer", self.mp)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["failed_items"]), 1)
        self.assertEqual(result["failed_items"][0]["listing_id"], "nonexistent")

    def test_checkout_all_fail_returns_failed_order(self):
        self._add("nonexistent", 50)
        result = self.mgr.checkout("buyer", self.mp)
        self.assertFalse(result["success"])
        self.assertEqual(result["order"]["status"], "failed")

    def test_checkout_partial_success_keeps_failed_items_in_cart(self):
        # One purchasable item, one that fails: only the purchased item should be
        # removed from the cart; the failed item must remain for retry.
        self._add("lst1", 100)
        self._add("nonexistent", 50, "owner1")
        result = self.mgr.checkout("buyer", self.mp)
        self.assertTrue(result["success"])
        remaining = self.mgr.get_cart("buyer")["items"]
        remaining_ids = [i["listing_id"] for i in remaining]
        self.assertEqual(remaining_ids, ["nonexistent"])

    def test_checkout_full_success_empties_cart(self):
        # When every item is purchased, the cart ends up empty.
        self._add("lst1", 100)
        self._add("lst2", 200, "owner2")
        result = self.mgr.checkout("buyer", self.mp)
        self.assertTrue(result["success"])
        self.assertEqual(self.mgr.get_cart("buyer")["items"], [])

    def test_checkout_order_items_expose_notification_fields(self):
        """Each order item must carry owner_id, listing_id, and name so the
        API layer can dispatch per-creator new_download notifications and
        issue license keys — the same fields download_avatar() has access to."""
        self._add("lst1", 100, "owner1")
        self._add("lst2", 200, "owner2")
        result = self.mgr.checkout("buyer", self.mp)
        for item in result["order"]["items"]:
            for field in ("listing_id", "owner_id", "name"):
                self.assertIn(field, item, f"order item missing '{field}' needed for notification dispatch")
        owner_ids = {i["owner_id"] for i in result["order"]["items"]}
        self.assertEqual(owner_ids, {"owner1", "owner2"})

    def test_get_order_by_id(self):
        self._add("lst1")
        result = self.mgr.checkout("buyer", self.mp)
        order_id = result["order"]["order_id"]
        fetched = self.mgr.get_order("buyer", order_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["order_id"], order_id)

    def test_get_order_wrong_user_returns_none(self):
        self._add("lst1")
        result = self.mgr.checkout("buyer", self.mp)
        order_id = result["order"]["order_id"]
        self.assertIsNone(self.mgr.get_order("other-user", order_id))

    def test_get_orders_pagination(self):
        for _ in range(5):
            self._add("lst1")
            self.mgr.checkout("buyer", self.mp)
        result = self.mgr.get_orders("buyer", limit=3, offset=0)
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["items"]), 3)
        self.assertTrue(result["has_more"])


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestCartManagerSingleton(unittest.TestCase):
    def test_singleton_same_instance(self):
        a = get_cart_manager()
        b = get_cart_manager()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
