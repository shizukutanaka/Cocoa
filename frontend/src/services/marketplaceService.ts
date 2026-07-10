import client from "./apiClient";
import type { Listing, Paginated, Review, ReviewsResponse } from "../types/api";

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

export async function listReviews(
  listingId: string,
  sortBy: "newest" | "helpful" | "rating_high" | "rating_low" = "newest"
): Promise<ReviewsResponse> {
  const { data } = await client.get(`/api/marketplace/${listingId}/reviews`, {
    params: { sort_by: sortBy, limit: 50, offset: 0 },
  });
  return data;
}

export async function postReview(listingId: string, stars: number, text: string) {
  const { data } = await client.post(`/api/marketplace/${listingId}/reviews`, { stars, text });
  return data as { listing_id: string; average_rating: number; review: Review };
}

export async function deleteMyReview(listingId: string) {
  await client.delete(`/api/marketplace/${listingId}/reviews/mine`);
}

export async function voteReviewHelpful(reviewId: string, helpful: boolean) {
  const { data } = await client.post(`/api/marketplace/reviews/${reviewId}/helpful`, { helpful });
  return data;
}
