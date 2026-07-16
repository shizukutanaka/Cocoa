import client from "./apiClient";
import type { CommissionRequest, Paginated } from "../types/api";

export async function createCommission(
  creatorId: string,
  title: string,
  description: string,
  budgetCredits: number
): Promise<CommissionRequest> {
  const { data } = await client.post("/api/commissions", {
    creator_id: creatorId,
    title,
    description,
    budget_credits: budgetCredits,
  });
  return data;
}

export async function listCommissionsReceived(limit = 50, offset = 0): Promise<Paginated<CommissionRequest>> {
  const { data } = await client.get("/api/commissions/received", { params: { limit, offset } });
  return data;
}

export async function listCommissionsSent(limit = 50, offset = 0): Promise<Paginated<CommissionRequest>> {
  const { data } = await client.get("/api/commissions/sent", { params: { limit, offset } });
  return data;
}

export async function respondToCommission(
  requestId: string,
  accept: boolean,
  note = ""
): Promise<CommissionRequest> {
  const { data } = await client.post(`/api/commissions/${requestId}/respond`, { accept, note });
  return data;
}

export async function deliverCommission(
  requestId: string,
  deliveryNote: string,
  deliveryListingId = ""
): Promise<CommissionRequest> {
  const { data } = await client.post(`/api/commissions/${requestId}/deliver`, {
    delivery_note: deliveryNote,
    delivery_listing_id: deliveryListingId,
  });
  return data;
}

export async function closeCommission(requestId: string): Promise<CommissionRequest> {
  const { data } = await client.post(`/api/commissions/${requestId}/close`);
  return data;
}

export async function disputeCommission(requestId: string, reason: string, details = "") {
  const { data } = await client.post(`/api/commissions/${requestId}/dispute`, { reason, details });
  return data;
}
