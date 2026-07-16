import client from "./apiClient";
import type { LicenseKey, Paginated } from "../types/api";

export async function getMyLicenses(limit = 50, offset = 0): Promise<Paginated<LicenseKey>> {
  const { data } = await client.get("/api/licenses/mine", { params: { limit, offset } });
  return data;
}

export async function activateLicense(keyId: string, note = ""): Promise<LicenseKey> {
  const { data } = await client.post(`/api/licenses/${keyId}/activate`, { note });
  return data;
}

export async function revokeLicense(keyId: string, reason = ""): Promise<LicenseKey> {
  const { data } = await client.post(`/api/licenses/${keyId}/revoke`, { reason });
  return data;
}

export async function getListingLicenses(listingId: string, limit = 100, offset = 0): Promise<Paginated<LicenseKey>> {
  const { data } = await client.get(`/api/marketplace/${listingId}/licenses`, { params: { limit, offset } });
  return data;
}
