import client from "./apiClient";
import type { NotificationsResponse } from "../types/api";

export async function listNotifications(unreadOnly = false, limit = 50, offset = 0): Promise<NotificationsResponse> {
  const { data } = await client.get("/api/notifications", { params: { unread_only: unreadOnly, limit, offset } });
  return data;
}

export async function unreadCount(): Promise<number> {
  const { data } = await client.get("/api/notifications/unread-count");
  return data.unread_count;
}

export async function markRead(notificationId: string) {
  await client.post(`/api/notifications/${notificationId}/read`);
}

export async function markAllRead() {
  const { data } = await client.post("/api/notifications/read-all");
  return data.marked_count as number;
}

export async function deleteNotification(notificationId: string) {
  await client.delete(`/api/notifications/${notificationId}`);
}

export async function getMutedKinds(): Promise<string[]> {
  const { data } = await client.get("/api/notifications/preferences");
  return data.muted_kinds ?? [];
}

export async function setMutedKinds(mutedKinds: string[]): Promise<string[]> {
  const { data } = await client.put("/api/notifications/preferences", { muted_kinds: mutedKinds });
  return data.muted_kinds ?? [];
}
