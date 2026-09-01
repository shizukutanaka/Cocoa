import { describe, it, expect, vi, beforeEach } from "vitest";
import client from "./apiClient";
import {
  listUsers,
  grantCredits,
  getAdminStats,
  listModerationItems,
  updateModerationStatus,
  setModerationPriority,
  changeUserRole,
  revokeCreatorVerification,
  getListingQuota,
  setListingQuota,
  getLedgerIntegrity,
} from "./adminService";

// The admin Users tab depends on these two request shapes exactly: the roster
// GET and the credit-grant POST payload. If either drifts from what
// main/api_server.py expects (GET /api/admin/users, POST /api/admin/credits/grant
// with {user_id, amount}), the tab breaks silently, so pin them here.
vi.mock("./apiClient", () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const mockClient = vi.mocked(client);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("listUsers", () => {
  it("GETs the admin roster endpoint and returns the payload", async () => {
    mockClient.get.mockResolvedValue({
      data: { users: [{ user_id: "u1", username: "alice" }], total: 1 },
    });
    const out = await listUsers();
    expect(mockClient.get).toHaveBeenCalledWith("/api/admin/users");
    expect(out.total).toBe(1);
    expect(out.users[0].username).toBe("alice");
  });
});

describe("grantCredits", () => {
  it("POSTs user_id and amount to the grant endpoint", async () => {
    mockClient.post.mockResolvedValue({
      data: { user_id: "u1", granted: 50, new_balance: 150 },
    });
    const out = await grantCredits("u1", 50);
    expect(mockClient.post).toHaveBeenCalledWith("/api/admin/credits/grant", {
      user_id: "u1",
      amount: 50,
    });
    expect(out.new_balance).toBe(150);
  });
});

describe("moderation queue (commission disputes)", () => {
  it("filters to the requested kind and sorts by priority", async () => {
    // The queue also mirrors listing/review reports and creator applications,
    // which have their own tabs -- without the kind filter the tab would show
    // every item twice over.
    mockClient.get.mockResolvedValue({ data: { items: [], total: 0 } });
    await listModerationItems("commission_dispute");
    expect(mockClient.get).toHaveBeenCalledWith("/api/admin/moderation", {
      params: {
        kind: "commission_dispute",
        status: undefined,
        limit: 50,
        offset: 0,
        sort_by: "priority",
      },
    });
  });

  it("PUTs status with the recorded reason", async () => {
    mockClient.put.mockResolvedValue({ data: { item_id: "i1", status: "resolved" } });
    await updateModerationStatus("i1", "resolved", "納品物を確認した");
    expect(mockClient.put).toHaveBeenCalledWith("/api/admin/moderation/i1/status", {
      status: "resolved",
      notes: "納品物を確認した",
    });
  });

  it("PUTs priority to the priority endpoint", async () => {
    mockClient.put.mockResolvedValue({ data: { item_id: "i1", priority: "high" } });
    await setModerationPriority("i1", "high");
    expect(mockClient.put).toHaveBeenCalledWith("/api/admin/moderation/i1/priority", {
      priority: "high",
    });
  });
});

describe("getAdminStats", () => {
  it("GETs the admin stats endpoint and returns the payload", async () => {
    mockClient.get.mockResolvedValue({
      data: { users: { total: 3, by_role: { admin: 1 }, active: 3, locked: 0 } },
    });
    const out = await getAdminStats();
    expect(mockClient.get).toHaveBeenCalledWith("/api/admin/stats");
    expect(out.users?.total).toBe(3);
  });

  it("passes the durability section through (a failing save must reach the UI)", async () => {
    mockClient.get.mockResolvedValue({
      data: {
        durability: {
          enabled: true, ok: false, last_attempt_at: "t1", last_success_at: "t0",
          error: "No space left on device", stores_in_last_snapshot: 15,
          interval_seconds: 30,
        },
      },
    });
    const out = await getAdminStats();
    expect(out.durability?.ok).toBe(false);
    expect(out.durability?.error).toContain("No space left");
  });
});

describe("account administration", () => {
  it("PUTs the new role to the role endpoint", async () => {
    mockClient.put.mockResolvedValue({ data: { user_id: "u1", new_role: "moderator" } });
    await changeUserRole("u1", "moderator");
    expect(mockClient.put).toHaveBeenCalledWith("/api/admin/users/u1/role", {
      new_role: "moderator",
    });
  });

  it("DELETEs to revoke a creator badge", async () => {
    // Granting happens through the application review flow; before this there
    // was no inverse at all (audit #73).
    mockClient.delete.mockResolvedValue({ data: { user_id: "u1", status: "revoked" } });
    await revokeCreatorVerification("u1");
    expect(mockClient.delete).toHaveBeenCalledWith("/api/admin/users/u1/verify-creator");
  });
});

describe("proportionate enforcement and money integrity", () => {
  it("GETs a user's publish quota", async () => {
    mockClient.get.mockResolvedValue({
      data: { user_id: "u1", max_listings: 5, current_active: 2 },
    });
    const out = await getListingQuota("u1");
    expect(mockClient.get).toHaveBeenCalledWith("/api/admin/quotas/u1");
    expect(out.max_listings).toBe(5);
  });

  it("POSTs a quota cap with the user_id and limit", async () => {
    mockClient.post.mockResolvedValue({ data: { user_id: "u1", max_listings: 3 } });
    await setListingQuota("u1", 3);
    expect(mockClient.post).toHaveBeenCalledWith("/api/admin/quotas/set", {
      user_id: "u1",
      max_listings: 3,
    });
  });

  it("sends -1 to lift a cap, which the server maps to unlimited", async () => {
    // The reversal path matters as much as the cap: enforcement that cannot be
    // undone is the trap #45 and #58 were about.
    mockClient.post.mockResolvedValue({ data: { user_id: "u1", max_listings: null } });
    await setListingQuota("u1", -1);
    expect(mockClient.post).toHaveBeenCalledWith("/api/admin/quotas/set", {
      user_id: "u1",
      max_listings: -1,
    });
  });

  it("GETs the credit ledger integrity audit", async () => {
    mockClient.get.mockResolvedValue({
      data: { consistent: true, users_checked: 12, discrepancy_count: 0, discrepancies: [] },
    });
    const out = await getLedgerIntegrity();
    expect(mockClient.get).toHaveBeenCalledWith("/api/admin/credits/integrity");
    expect(out.consistent).toBe(true);
  });
});
