import { describe, it, expect, vi, beforeEach } from "vitest";
import client from "./apiClient";
import { listUsers, grantCredits, getAdminStats } from "./adminService";

// The admin Users tab depends on these two request shapes exactly: the roster
// GET and the credit-grant POST payload. If either drifts from what
// main/api_server.py expects (GET /api/admin/users, POST /api/admin/credits/grant
// with {user_id, amount}), the tab breaks silently, so pin them here.
vi.mock("./apiClient", () => ({
  default: { get: vi.fn(), post: vi.fn() },
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

describe("getAdminStats", () => {
  it("GETs the admin stats endpoint and returns the payload", async () => {
    mockClient.get.mockResolvedValue({
      data: { users: { total: 3, by_role: { admin: 1 }, active: 3, locked: 0 } },
    });
    const out = await getAdminStats();
    expect(mockClient.get).toHaveBeenCalledWith("/api/admin/stats");
    expect(out.users?.total).toBe(3);
  });
});
