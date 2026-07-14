import client, { newIdempotencyKey } from "./apiClient";
import type { Bundle, BundlePurchaseResult, Paginated } from "../types/api";

export interface BundleCreateInput {
  name: string;
  description?: string;
  listing_ids: string[];
  discount_percent: number;
}

export async function listActiveBundles(limit = 50, offset = 0): Promise<Paginated<Bundle>> {
  const { data } = await client.get("/api/bundles", { params: { limit, offset } });
  return data;
}

export async function getBundle(bundleId: string): Promise<Bundle> {
  const { data } = await client.get(`/api/bundles/${bundleId}`);
  return data;
}

export async function listMyBundles(includeInactive = true, limit = 50, offset = 0): Promise<Paginated<Bundle>> {
  const { data } = await client.get("/api/bundles/mine", {
    params: { include_inactive: includeInactive, limit, offset },
  });
  return data;
}

export async function createBundle(input: BundleCreateInput): Promise<Bundle> {
  const { data } = await client.post("/api/bundles", input);
  return data;
}

export async function deleteBundle(bundleId: string) {
  await client.delete(`/api/bundles/${bundleId}`);
}

export async function deactivateBundle(bundleId: string): Promise<Bundle> {
  const { data } = await client.post(`/api/bundles/${bundleId}/deactivate`);
  return data;
}

export async function activateBundle(bundleId: string): Promise<Bundle> {
  const { data } = await client.post(`/api/bundles/${bundleId}/activate`);
  return data;
}

export async function purchaseBundle(bundleId: string): Promise<BundlePurchaseResult> {
  const { data } = await client.post(
    `/api/bundles/${bundleId}/purchase`,
    {},
    { headers: { "Idempotency-Key": newIdempotencyKey() } }
  );
  return data;
}
