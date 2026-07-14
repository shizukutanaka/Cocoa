import client, { newIdempotencyKey } from "./apiClient";
import type { Paginated, Tip } from "../types/api";

export async function sendTip(recipientId: string, amount: number, message = ""): Promise<Tip> {
  const { data } = await client.post(
    "/api/tips",
    { recipient_id: recipientId, amount, message },
    { headers: { "Idempotency-Key": newIdempotencyKey() } }
  );
  return data;
}

export async function getTipsReceived(limit = 20, offset = 0): Promise<Paginated<Tip>> {
  const { data } = await client.get("/api/tips/received", { params: { limit, offset } });
  return data;
}

export async function getTipsSent(limit = 20, offset = 0): Promise<Paginated<Tip>> {
  const { data } = await client.get("/api/tips/sent", { params: { limit, offset } });
  return data;
}
