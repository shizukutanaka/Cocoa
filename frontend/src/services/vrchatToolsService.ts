import client from "./apiClient";
import type { VRChatBudgetResult, VRChatPerformanceResult } from "../types/api";

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

export interface VRChatStatsInput {
  polygons: number;
  materials: number;
  bones: number;
  physbones_components: number;
  physbones_colliders: number;
  texture_memory_mb: number;
  platform: "PC" | "Quest";
}

// POST /api/tools/vrchat/performance — public, no auth required.
export async function analyzePerformance(stats: VRChatStatsInput): Promise<VRChatPerformanceResult> {
  const { data } = await client.post("/api/tools/vrchat/performance", stats);
  return data;
}
