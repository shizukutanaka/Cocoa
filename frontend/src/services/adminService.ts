import client from "./apiClient";
import type {
  AdminStats,
  AdminUser,
  BannedUser,
  ModerationItem,
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

// --- Seller-level enforcement ---

// Escalation beyond a single takedown. Removing one listing does nothing about
// a seller who simply publishes again, so enforcement has to be able to act on
// the account once the record justifies it.
export async function banUser(userId: string, reason: string) {
  const { data } = await client.post(`/api/admin/users/${userId}/ban`, { reason });
  return data;
}

export async function unbanUser(userId: string) {
  const { data } = await client.delete(`/api/admin/users/${userId}/ban`);
  return data;
}

export async function listBannedUsers(limit = 50, offset = 0): Promise<Paginated<BannedUser>> {
  const { data } = await client.get("/api/admin/users/banned", { params: { limit, offset } });
  return data;
}

// --- Overview ---

// Platform stats for the console landing. Admin/moderator only (server-enforced).
export async function getAdminStats(): Promise<AdminStats> {
  const { data } = await client.get("/api/admin/stats");
  return data;
}

// --- User administration ---

// GET /api/admin/users returns the whole roster (no server-side paging); the
// tab filters client-side. Admin/moderator only (server-enforced).
export async function listUsers(): Promise<{ users: AdminUser[]; total: number }> {
  const { data } = await client.get("/api/admin/users");
  return data;
}

// Grant in-app credits (a support/comp action -- the same credit ledger that
// refunds move, NOT real money). The server caps the per-grant amount and
// records it to the ledger. Returns the recipient's new balance.
export async function grantCredits(
  userId: string,
  amount: number,
): Promise<{ user_id: string; granted: number; new_balance: number }> {
  const { data } = await client.post("/api/admin/credits/grant", {
    user_id: userId,
    amount,
  });
  return data;
}

// --- Moderation queue ---

/**
 * The unified queue mirrors listing reports, review reports and creator
 * applications -- all of which already have their own tab -- but
 * `commission_dispute` items are enqueued ONLY here (api_server
 * report_commission_problem). Without this call a dispute over paid
 * commission work sits in the queue forever with no way to adjudicate it,
 * the same dead end #46 fixed for listing reports.
 */
export async function listModerationItems(
  kind?: string,
  status?: string,
  limit = 50,
  offset = 0,
): Promise<Paginated<ModerationItem>> {
  const { data } = await client.get("/api/admin/moderation", {
    params: { kind, status, limit, offset, sort_by: "priority" },
  });
  return data;
}

export async function updateModerationStatus(
  itemId: string,
  status: "in_review" | "resolved" | "dismissed",
  notes = "",
) {
  const { data } = await client.put(`/api/admin/moderation/${itemId}/status`, {
    status,
    notes,
  });
  return data;
}

export async function setModerationPriority(itemId: string, priority: "low" | "medium" | "high") {
  const { data } = await client.put(`/api/admin/moderation/${itemId}/priority`, { priority });
  return data;
}

export async function assignModerationItem(itemId: string, adminId: string) {
  const { data } = await client.put(`/api/admin/moderation/${itemId}/assign`, {
    admin_id: adminId,
  });
  return data;
}

// Change another account's role. Admin only (server-side: change_role calls
// require_role("admin"), so a moderator gets 403). The server refuses to change
// the caller's OWN role or to demote the last remaining admin -- both are
// unrecoverable lockouts (audit #73).
export async function changeUserRole(userId: string, newRole: "user" | "moderator" | "admin") {
  const { data } = await client.put(`/api/admin/users/${userId}/role`, { new_role: newRole });
  return data;
}

// Take back a creator badge. The badge is granted through the application
// review flow, which had no inverse -- the same missing-reversal gap #45 fixed
// for takedowns and #58 for bans.
export async function revokeCreatorVerification(userId: string) {
  const { data } = await client.delete(`/api/admin/users/${userId}/verify-creator`);
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
