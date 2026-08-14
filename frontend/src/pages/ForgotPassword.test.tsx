import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ForgotPassword } from "./ForgotPassword";
import { renderWithProviders } from "../test/renderWithProviders";
import * as authService from "../services/authService";

vi.mock("../services/authService");

const requestPasswordReset = vi.mocked(authService.requestPasswordReset);

describe("ForgotPassword", () => {
  beforeEach(() => vi.resetAllMocks());

  it("answers identically whether or not the address is registered", async () => {
    // Account enumeration defence: the server returns a uniform {status:"sent"}
    // for known and unknown addresses (FEATURE_AUDIT.md #42), and the UI must
    // not undo that by wording the two cases differently.
    const user = userEvent.setup();
    requestPasswordReset.mockResolvedValue({ status: "sent" });

    renderWithProviders(<ForgotPassword />);
    await user.type(screen.getByLabelText("メールアドレス"), "nobody@example.com");
    await user.click(screen.getByRole("button", { name: "再設定リンクを送る" }));

    expect(await screen.findByText(/登録されている場合/)).toBeInTheDocument();
    expect(requestPasswordReset).toHaveBeenCalledWith("nobody@example.com");
  });

  it("does not show a token when the server withholds one (production)", async () => {
    const user = userEvent.setup();
    requestPasswordReset.mockResolvedValue({ status: "sent" });

    renderWithProviders(<ForgotPassword />);
    await user.type(screen.getByLabelText("メールアドレス"), "someone@example.com");
    await user.click(screen.getByRole("button", { name: "再設定リンクを送る" }));

    await screen.findByText(/登録されている場合/);
    // Since #51 the link is emailed; a token block here would mean the secret
    // leaked into the API response.
    expect(screen.queryByText(/開発用トークン/)).not.toBeInTheDocument();
  });

  it("offers the dev shortcut only when the server exposes a token", async () => {
    const user = userEvent.setup();
    requestPasswordReset.mockResolvedValue({ status: "sent", dev_token: "tok-abc" });

    renderWithProviders(<ForgotPassword />);
    await user.type(screen.getByLabelText("メールアドレス"), "dev@example.com");
    await user.click(screen.getByRole("button", { name: "再設定リンクを送る" }));

    expect(await screen.findByText(/開発用トークン/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /このトークンで再設定に進む/ })).toHaveAttribute(
      "href",
      "/reset-password?token=tok-abc",
    );
  });

  it("reports a failure instead of claiming the mail was sent", async () => {
    const user = userEvent.setup();
    requestPasswordReset.mockRejectedValue(new Error("network down"));

    renderWithProviders(<ForgotPassword />);
    await user.type(screen.getByLabelText("メールアドレス"), "a@example.com");
    await user.click(screen.getByRole("button", { name: "再設定リンクを送る" }));

    expect(await screen.findByText(/リクエストに失敗しました/)).toBeInTheDocument();
    expect(screen.queryByText(/登録されている場合/)).not.toBeInTheDocument();
  });
});
