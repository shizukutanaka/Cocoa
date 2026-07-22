import client from "./apiClient";
import type { Listing, Paginated, PublicProfile, Storefront } from "../types/api";

export async function getPublicProfile(userId: string): Promise<PublicProfile> {
  const { data } = await client.get(`/api/users/${userId}/profile`);
  return data;
}

export async function searchUsers(q: string, limit = 10): Promise<{ items: PublicProfile[]; total: number }> {
  const { data } = await client.get("/api/users/search", { params: { q, limit } });
  return data;
}

export async function getStorefront(userId: string, listingLimit = 20): Promise<Storefront> {
  const { data } = await client.get(`/api/users/${userId}/storefront`, {
    params: { listing_limit: listingLimit },
  });
  return data;
}

export async function getMyFollowing(): Promise<PublicProfile[]> {
  const { data } = await client.get("/api/auth/following");
  return data.following ?? [];
}

export async function followCreator(creatorId: string) {
  const { data } = await client.post(`/api/auth/following/${creatorId}`);
  return data as { following_count: number; followed: string };
}

export async function unfollowCreator(creatorId: string) {
  const { data } = await client.delete(`/api/auth/following/${creatorId}`);
  return data as { following_count: number; unfollowed: string };
}

export async function getFeed(limit = 20, offset = 0): Promise<Paginated<Listing>> {
  const { data } = await client.get("/api/auth/feed", { params: { limit, offset } });
  return data;
}

// Public list of the users who follow this creator.
export async function getFollowers(userId: string): Promise<{ items: PublicProfile[]; total: number }> {
  const { data } = await client.get(`/api/users/${userId}/followers`);
  return { items: data.items ?? [], total: data.total ?? 0 };
}

// Public list of the creators this user follows.
export async function getFollowing(userId: string): Promise<{ items: PublicProfile[]; total: number }> {
  const { data } = await client.get(`/api/users/${userId}/following`);
  return { items: data.items ?? [], total: data.total ?? 0 };
}
