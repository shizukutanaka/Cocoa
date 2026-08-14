import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VerifyEmail } from "./VerifyEmail";
import { renderWithProviders } from "../test/renderWithProviders";
import * as authService from "../services/authService";

vi.mock("../services/authService");

const verifyEmail = vi.mocked(authService.verifyEmail);

/**
 * Landing page for the link in the verification email (FEATURE_AUDIT.md #51).
 * The token is the credential, so the page must work for a signed-out visitor
 * -- these tests render it without a logged-in user for exactly that reason.
 */
describe("VerifyEmail", () => {
  beforeEach(() => vi.resetAllMocks());

  it("pre-fills the token carried by the emailed link", () => {
    renderWithProviders(<VerifyEmail />, {
      initialEntries: ["/verify-email?token=tok-from-email"],
    });
    expect(screen.getByLabelText("確認コード")).toHaveValue("tok-from-email");
  });

  it("confirms the address and submits the token from the link", async () => {
    const user = userEvent.setup();
    verifyEmail.mockResolvedValue({ status: "verified" });

    renderWithProviders(<VerifyEmail />, { initialEntries: ["/verify-email?token=tok-abc"] });
    await user.click(screen.getByRole("button", { name: "メールアドレスを確認する" }));

    expect(verifyEmail).toHaveBeenCalledWith("tok-abc");
    expect(await screen.findByText("メールアドレスを確認しました")).toBeInTheDocument();
  });

  it("accepts a manually typed code when arriving without a link", async () => {
    const user = userEvent.setup();
    verifyEmail.mockResolvedValue({ status: "verified" });

    renderWithProviders(<VerifyEmail />, { initialEntries: ["/verify-email"] });
    const field = screen.getByLabelText("確認コード");
    expect(field).toHaveValue("");

    await user.type(field, "  typed-code  ");
    await user.click(screen.getByRole("button", { name: "メールアドレスを確認する" }));

    // Trimmed, so a code copied out of an email with stray whitespace works.
    expect(verifyEmail).toHaveBeenCalledWith("typed-code");
  });

  it("explains an expired or invalid token instead of showing success", async () => {
    const user = userEvent.setup();
    verifyEmail.mockRejectedValue(new Error("bad token"));

    renderWithProviders(<VerifyEmail />, { initialEntries: ["/verify-email?token=stale"] });
    await user.click(screen.getByRole("button", { name: "メールアドレスを確認する" }));

    expect(await screen.findByText(/無効または期限切れ/)).toBeInTheDocument();
    expect(screen.queryByText("メールアドレスを確認しました")).not.toBeInTheDocument();
  });
});
