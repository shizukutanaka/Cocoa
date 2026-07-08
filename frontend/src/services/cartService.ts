import client, { newIdempotencyKey } from "./apiClient";
import type { Cart, CheckoutResult, Order, Paginated } from "../types/api";

export async function getCart(): Promise<Cart> {
  const { data } = await client.get("/api/cart");
  return data;
}

export async function addToCart(listingId: string, promoCode = ""): Promise<Cart> {
  const { data } = await client.post("/api/cart/items", { listing_id: listingId, promo_code: promoCode });
  return data;
}

export async function removeFromCart(listingId: string): Promise<Cart> {
  const { data } = await client.delete(`/api/cart/items/${listingId}`);
  return data;
}

export async function clearCart(): Promise<void> {
  await client.delete("/api/cart");
}

export async function setCartItemPromo(listingId: string, promoCode: string): Promise<Cart> {
  const { data } = await client.put(`/api/cart/items/${listingId}/promo`, { promo_code: promoCode });
  return data;
}

/** Generates a fresh Idempotency-Key per checkout attempt series (retries of
 * THE SAME attempt should reuse the key the caller passes in, not generate a
 * new one -- see checkout_cart's Idempotency-Key handling in api_server.py). */
export async function checkout(idempotencyKey = newIdempotencyKey()): Promise<CheckoutResult> {
  const { data } = await client.post(
    "/api/cart/checkout",
    {},
    { headers: { "Idempotency-Key": idempotencyKey } }
  );
  return data;
}

export async function getOrders(limit = 20, offset = 0): Promise<Paginated<Order>> {
  const { data } = await client.get("/api/orders", { params: { limit, offset } });
  return data;
}
