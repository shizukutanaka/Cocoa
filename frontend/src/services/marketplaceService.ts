import client from "./apiClient";
import type { Listing, Paginated } from "../types/api";

export interface BrowseParams {
  q?: string;
  tags?: string;
  category?: string;
  sort_by?: "newest" | "downloads" | "rating" | "price_asc" | "price_desc";
  limit?: number;
  offset?: number;
  is_free?: boolean;
  platform?: string;
}

export async function browseMarketplace(params: BrowseParams): Promise<Paginated<Listing>> {
  const { data } = await client.get("/api/marketplace", { params });
  return data;
}

export async function getListing(listingId: string): Promise<Listing> {
  const { data } = await client.get(`/api/marketplace/${listingId}`);
  return data;
}

export async function getFeatured(limit = 12): Promise<{ items: Listing[]; total: number }> {
  const { data } = await client.get("/api/marketplace/featured", { params: { limit } });
  return data;
}

export async function addFavorite(listingId: string) {
  await client.post(`/api/marketplace/${listingId}/favorite`);
}

export async function removeFavorite(listingId: string) {
  await client.delete(`/api/marketplace/${listingId}/favorite`);
}

export async function listFavorites(): Promise<{ items: Listing[]; total: number }> {
  const { data } = await client.get("/api/marketplace/favorites");
  return data;
}
