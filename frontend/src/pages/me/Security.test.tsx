import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { Security } from "./Security";
import { renderWithProviders } from "../../test/renderWithProviders";
import * as authService from "../../services/authService";
import * as userService from "../../services/userService";

vi.mock("../../services/authService");
vi.mock("../../services/userService");
vi.mock("../../hooks/useAuth", async () => {
  const actual = await vi.importActual<typeof import("../../hooks/useAuth")>("../../hooks/useAuth");
  return {
    ...actual,
    useAuth: () => ({
      user: { user_id: "u1", username: "alice", role: "user" },
      logout: vi.fn(),
      refresh: vi.fn(),
    }),
  };
});

const getTwoFactorStatus = vi.mocked(authService.getTwoFactorStatus);
const listApiKeys = vi.mocked(authService.listApiKeys);
const getPublicProfile = vi.mocked(userService.getPublicProfile);

/**
 * A deployment without COCOA_2FA_SECRET reports available:false (the endpoint
 * answers 200 -- "2FA is off and isn't offered here" is an answer, not a
 * server error). The page must say so rather than presenting 2FA as merely
 * switched off, which is what it did while the endpoint 500'd.
 */
describe("Security — 2FA availability", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    listApiKeys.mockResolvedValue({ items: [], total: 0 });
    getPublicProfile.mockResolvedValue({
      user_id: "u1",
      username: "alice",
      display_name: "Alice",
      bio: "",
      avatar_url: "",
      website_url: "",
      social_links: {},
      role: "user",
      is_email_verified: true,
      is_creator_verified: false,
      created_at: new Date().toISOString(),
    });
  });

  it("explains that 2FA is unavailable on an unconfigured deployment", async () => {
    getTwoFactorStatus.mockResolvedValue({ is_enabled: false, available: false });

    renderWithProviders(<Security />);

    expect(await screen.findByText(/2要素認証を利用できません/)).toBeInTheDocument();
    expect(screen.getByText("利用不可")).toBeInTheDocument();
    // Offering setup here would only produce a 501 once the user committed.
    expect(screen.queryByRole("button", { name: "2要素認証を設定する" })).not.toBeInTheDocument();
  });

  it("offers setup when the deployment does support 2FA", async () => {
    getTwoFactorStatus.mockResolvedValue({ is_enabled: false, available: true });

    renderWithProviders(<Security />);

    expect(await screen.findByRole("button", { name: "2要素認証を設定する" })).toBeInTheDocument();
    expect(screen.queryByText(/2要素認証を利用できません/)).not.toBeInTheDocument();
    expect(screen.getByText("無効")).toBeInTheDocument();
  });

  it("shows 2FA as enabled without the unavailable notice", async () => {
    getTwoFactorStatus.mockResolvedValue({ is_enabled: true, available: true });

    renderWithProviders(<Security />);

    expect(await screen.findByText("有効")).toBeInTheDocument();
    expect(screen.queryByText(/2要素認証を利用できません/)).not.toBeInTheDocument();
  });
});
