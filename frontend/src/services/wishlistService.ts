import client from "./apiClient";
import type { Paginated, WishlistItem } from "../types/api";

export async function getWishlist(withStatus = true): Promise<Paginated<WishlistItem>> {
  const { data } = await client.get("/api/wishlist", { params: { with_status: withStatus, limit: 100, offset: 0 } });
  return data;
}

export async function addToWishlist(listingId: string) {
  const { data } = await client.put(`/api/wishlist/${listingId}`);
  return data;
}

export async function removeFromWishlist(listingId: string) {
  await client.delete(`/api/wishlist/${listingId}`);
}

export async function checkWishlist(listingId: string): Promise<boolean> {
  const { data } = await client.get(`/api/wishlist/${listingId}/check`);
  return data.in_wishlist;
}
