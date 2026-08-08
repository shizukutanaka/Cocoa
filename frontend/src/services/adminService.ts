import client from "./apiClient";
import type {
  CreatorApplication,
  ListingReport,
  Paginated,
  RefundRequestRecord,
  ReportStats,
  ReviewReportRecord,
} from "../types/api";

/**
 * Admin / moderator endpoints. These require a role of `admin` or `moderator`
 * (main/api_server.py get_current_admin); the server is the authority -- the
 * client-side role check only decides whether to show the UI.
 */

// --- Listing reports ---

export async function listReports(
  status?: string,
  limit = 50,
  offset = 0,
): Promise<Paginated<ListingReport>> {
  const { data } = await client.get("/api/admin/reports", { params: { status, limit, offset } });
  return data;
}

export async function getReportStats(): Promise<ReportStats> {
  const { data } = await client.get("/api/admin/reports/stats");
  return data;
}

export async function resolveReport(
  reportId: string,
  action: "resolved" | "dismissed",
  note = "",
  takedown = false,
) {
  const { data } = await client.post(`/api/admin/reports/${reportId}/resolve`, {
    action,
    note,
    takedown,
  });
  return data;
}

// Undo a takedown. Added alongside the console so an incorrect moderation
// decision is recoverable (see FEATURE_AUDIT.md #45).
export async function restoreListing(listingId: string) {
  const { data } = await client.post(`/api/admin/listings/${listingId}/restore`);
  return data;
}

// --- Review reports ---

export async function listReviewReports(
  status?: string,
  limit = 50,
  offset = 0,
): Promise<Paginated<ReviewReportRecord>> {
  const { data } = await client.get("/api/admin/review-reports", { params: { status, limit, offset } });
  return data;
}

export async function resolveReviewReport(
  reportId: string,
  action: "resolved" | "dismissed",
  note = "",
  hide = false,
) {
  const { data } = await client.post(`/api/admin/review-reports/${reportId}/resolve`, {
    action,
    note,
    hide,
  });
  return data;
}

// --- Creator verification applications ---

export async function listCreatorApplications(
  status?: string,
  limit = 50,
  offset = 0,
): Promise<Paginated<CreatorApplication>> {
  const { data } = await client.get("/api/admin/creator-applications", {
    params: { status, limit, offset },
  });
  return data;
}

export async function reviewCreatorApplication(
  applicationId: string,
  decision: "approved" | "rejected",
  note = "",
) {
  const { data } = await client.post(
    `/api/admin/creator-applications/${applicationId}/review`,
    { decision, note },
  );
  return data;
}

// --- Refunds ---

export async function listRefunds(
  status?: string,
  limit = 50,
  offset = 0,
): Promise<Paginated<RefundRequestRecord>> {
  const { data } = await client.get("/api/admin/refunds", { params: { status, limit, offset } });
  return data;
}

export async function approveRefund(requestId: string) {
  const { data } = await client.post(`/api/admin/refunds/${requestId}/approve`);
  return data;
}

export async function rejectRefund(requestId: string, notes = "") {
  const { data } = await client.post(`/api/admin/refunds/${requestId}/reject`, { notes });
  return data;
}

/**
 * Triage order for report reasons. Moderation guidance is consistent that the
 * queue should surface the highest-risk items first rather than acting in
 * arrival order, so reports that can cause legal or security harm outrank
 * taste-level complaints.
 */
export const REASON_SEVERITY: Record<string, number> = {
  malware: 0,
  copyright: 1,
  inappropriate: 2,
  offensive: 2,
  misleading: 3,
  false_info: 3,
  spam: 4,
  other: 5,
};

export function severityOf(reason: string): number {
  return REASON_SEVERITY[reason] ?? 5;
}

export const SEVERITY_LABEL: Record<number, string> = {
  0: "最優先",
  1: "高",
  2: "高",
  3: "中",
  4: "低",
  5: "低",
};
