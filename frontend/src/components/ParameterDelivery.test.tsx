import { describe, it, expect, vi, afterEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ParameterDelivery } from "./ParameterDelivery";
import { renderWithProviders } from "../test/renderWithProviders";
import type { AvatarData } from "../types/api";

const PARAMS = { hair_length: 0.73, eye_color: "#3aa7ff", height_cm: 158 };

function avatarData(overrides: Partial<AvatarData> = {}): AvatarData {
  return {
    source_listing_id: "l1",
    source_avatar_id: "av1",
    name: "Test Avatar (copy)",
    parameters: PARAMS,
    tags: ["cute"],
    category: "avatar",
    thumbnail_url: "",
    amount_paid: 0,
    seller_id: "u1",
    ...overrides,
  };
}

/**
 * This panel IS the buyer's delivery of the product (FEATURE_AUDIT.md #44):
 * Cocoa trades avatar parameter sets, and before this component existed a
 * completed purchase gave the buyer no way to obtain what they paid for.
 */
describe("ParameterDelivery", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows the purchased parameters and how many there are", () => {
    renderWithProviders(<ParameterDelivery data={avatarData()} />);
    expect(screen.getByText(/3 項目/)).toBeInTheDocument();
    const shown = JSON.parse(screen.getByText(/hair_length/).textContent ?? "{}");
    expect(shown).toEqual(PARAMS);
  });

  it("hands the exact published JSON to the clipboard", async () => {
    // userEvent.setup() installs its own clipboard stub, so assert on what
    // actually landed there rather than spying on the call.
    const user = userEvent.setup();
    renderWithProviders(<ParameterDelivery data={avatarData()} />);

    await user.click(screen.getByRole("button", { name: "JSONをコピー" }));

    expect(JSON.parse(await navigator.clipboard.readText())).toEqual(PARAMS);
    // The button confirms the copy back to the user.
    expect(await screen.findByRole("button", { name: "コピーしました" })).toBeInTheDocument();
  });

  it("tells a first-time buyer what they were charged and that re-access is free", () => {
    renderWithProviders(<ParameterDelivery data={avatarData({ amount_paid: 12 })} />);
    expect(screen.getByText(/12 クレジットを支払いました/)).toBeInTheDocument();
    expect(screen.getByText(/再取得は無料/)).toBeInTheDocument();
  });

  it("states that nothing was charged on a free re-retrieval", () => {
    // Re-downloads are free forever (avatar_marketplace.py sets paid=False),
    // so the panel must not imply a second charge.
    renderWithProviders(<ParameterDelivery data={avatarData({ amount_paid: 0 })} />);
    expect(screen.getByText(/追加の支払いはありません/)).toBeInTheDocument();
    expect(screen.queryByText(/クレジットを支払いました/)).not.toBeInTheDocument();
  });

  it("explains an empty parameter set instead of rendering a blank block", () => {
    renderWithProviders(<ParameterDelivery data={avatarData({ parameters: {} })} />);
    expect(screen.getByText(/パラメータが登録されていません/)).toBeInTheDocument();
  });

  it("offers a close control only when the caller supplies one", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    const { unmount } = renderWithProviders(
      <ParameterDelivery data={avatarData()} onClose={onClose} />,
    );
    await user.click(screen.getByRole("button", { name: "閉じる" }));
    expect(onClose).toHaveBeenCalled();
    unmount();

    renderWithProviders(<ParameterDelivery data={avatarData()} />);
    expect(screen.queryByRole("button", { name: "閉じる" })).not.toBeInTheDocument();
  });
});
