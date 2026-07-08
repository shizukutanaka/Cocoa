import client from "./apiClient";
import type { Collection, CollectionItemStatus, Paginated } from "../types/api";

export async function myCollections(limit = 50, offset = 0): Promise<Paginated<Collection>> {
  const { data } = await client.get("/api/collections/mine", { params: { limit, offset } });
  return data;
}

export async function createCollection(name: string, description = "", isPublic = false): Promise<Collection> {
  const { data } = await client.post("/api/collections", { name, description, is_public: isPublic });
  return data;
}

export async function getCollection(collectionId: string): Promise<Collection> {
  const { data } = await client.get(`/api/collections/${collectionId}`);
  return data;
}

export async function getCollectionItems(collectionId: string, limit = 50, offset = 0): Promise<Paginated<CollectionItemStatus>> {
  const { data } = await client.get(`/api/collections/${collectionId}/items`, { params: { limit, offset } });
  return data;
}

export async function addItemToCollection(collectionId: string, itemId: string) {
  await client.post(`/api/collections/${collectionId}/items/${itemId}`);
}

export async function removeItemFromCollection(collectionId: string, itemId: string) {
  await client.delete(`/api/collections/${collectionId}/items/${itemId}`);
}

export async function deleteCollection(collectionId: string) {
  await client.delete(`/api/collections/${collectionId}`);
}
