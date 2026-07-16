import client from "./apiClient";
import type { CreditHistoryEntry, Paginated } from "../types/api";

export async function getBalance(): Promise<number> {
  const { data } = await client.get("/api/credits/balance");
  return data.balance;
}

export async function getHistory(limit = 50, offset = 0): Promise<Paginated<CreditHistoryEntry>> {
  const { data } = await client.get("/api/credits/history", { params: { limit, offset } });
  return data;
}
