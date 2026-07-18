import client from "./apiClient";
import type { VRChatBudgetResult } from "../types/api";

export interface VRChatParameter {
  name: string;
  type: "Bool" | "Int" | "Float" | "Trigger";
  synced: boolean;
}

// POST /api/tools/vrchat/budget — public, no auth required.
export async function analyzeBudget(parameters: VRChatParameter[]): Promise<VRChatBudgetResult> {
  const { data } = await client.post("/api/tools/vrchat/budget", { parameters });
  return data;
}
