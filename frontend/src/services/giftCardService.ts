import client, { newIdempotencyKey } from "./apiClient";
import type { GiftCard, GiftCardRedeemResult, Paginated } from "../types/api";

export async function purchaseGiftCard(amount: number, message = ""): Promise<GiftCard> {
  const { data } = await client.post(
    "/api/gift-cards",
    { amount, message },
    { headers: { "Idempotency-Key": newIdempotencyKey() } }
  );
  return data;
}

export async function myGiftCards(limit = 50, offset = 0): Promise<Paginated<GiftCard>> {
  const { data } = await client.get("/api/gift-cards/mine", { params: { limit, offset } });
  return data;
}

export async function redeemGiftCard(code: string): Promise<GiftCardRedeemResult> {
  const { data } = await client.post(
    "/api/gift-cards/redeem",
    { code },
    { headers: { "Idempotency-Key": newIdempotencyKey() } }
  );
  return data;
}
