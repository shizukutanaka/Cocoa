import client from "./apiClient";
import type { Membership } from "../types/api";

export async function getMyMembership(): Promise<Membership> {
  const { data } = await client.get("/api/membership");
  return data;
}
