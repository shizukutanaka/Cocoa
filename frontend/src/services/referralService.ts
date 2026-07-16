import client from "./apiClient";
import type { Paginated, ReferralRecord, ReferralStats } from "../types/api";

export async function getMyCode(): Promise<{ code: string; user_id: string }> {
  const { data } = await client.get("/api/referrals/my-code");
  return data;
}

export async function getMyReferrals(limit = 50, offset = 0): Promise<Paginated<ReferralRecord>> {
  const { data } = await client.get("/api/referrals/my-referrals", { params: { limit, offset } });
  return data;
}

export async function getMyStats(): Promise<ReferralStats> {
  const { data } = await client.get("/api/referrals/my-stats");
  return data;
}

export async function getHowIJoined(): Promise<ReferralRecord | null> {
  const { data } = await client.get("/api/referrals/how-i-joined");
  return data;
}
