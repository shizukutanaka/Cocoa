import client from "./apiClient";
import type { Paginated, RefundRequestRecord } from "../types/api";

export async function requestRefund(orderId: string, reason: string): Promise<RefundRequestRecord> {
  const { data } = await client.post("/api/refunds", { order_id: orderId, reason });
  return data;
}

export async function getMyRefunds(limit = 50, offset = 0): Promise<Paginated<RefundRequestRecord>> {
  const { data } = await client.get("/api/refunds/mine", { params: { limit, offset } });
  return data;
}
