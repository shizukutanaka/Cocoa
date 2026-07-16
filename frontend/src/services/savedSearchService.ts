import client from "./apiClient";
import type { SavedSearch, SavedSearchFilters } from "../types/api";

export async function listSavedSearches(): Promise<{ items: SavedSearch[]; total: number }> {
  const { data } = await client.get("/api/search/saved");
  return data;
}

export async function createSavedSearch(
  name: string,
  query: string,
  filters: SavedSearchFilters
): Promise<SavedSearch> {
  const { data } = await client.post("/api/search/saved", { name, query, filters });
  return data;
}

export async function deleteSavedSearch(searchId: string) {
  await client.delete(`/api/search/saved/${searchId}`);
}

export async function setSavedSearchNotify(searchId: string, enabled: boolean): Promise<SavedSearch> {
  const { data } = await client.put(`/api/search/saved/${searchId}/notify`, null, {
    params: { enabled },
  });
  return data;
}
