import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError, AxiosHeaders } from "axios";
import { LoadError } from "./LoadError";

/**
 * An outage must not read as "you have nothing" (audit #100).
 *
 * #47 removed that anti-pattern from the server -- an unavailable subsystem
 * answers 503 rather than an empty 200. But a failed query leaves `data`
 * undefined, and pages rendered `!data || items.length === 0` as their empty
 * state, so a seller who owned listings was told 「まだ出品がありません」
 * during a 503. Measured in a browser before this component existed.
 */
function axiosErrorWith(status: number, data: unknown): AxiosError {
  const config = { headers: new AxiosHeaders() };
  const err = new AxiosError("request failed", "ERR_BAD_RESPONSE", config);
  err.response = { status, statusText: "", data, headers: {}, config } as AxiosError["response"];
  return err;
}

describe("LoadError", () => {
  it("shows the server's own reason for the failure", () => {
    render(<LoadError error={axiosErrorWith(503, { detail: "マーケットプレイスが利用できません" })} />);
    expect(screen.getByRole("alert")).toHaveTextContent("マーケットプレイスが利用できません");
  });

  it("explains a bare 503 as a temporary outage rather than emptiness", () => {
    render(<LoadError error={axiosErrorWith(503, {})} />);
    expect(screen.getByRole("alert")).toHaveTextContent("サービスが一時的に利用できません");
  });

  it("never claims the user has no data", () => {
    render(<LoadError error={axiosErrorWith(503, {})} />);
    const text = screen.getByRole("alert").textContent ?? "";
    for (const lie of ["ありません", "まだ"]) {
      expect(text).not.toContain(lie);
    }
  });

  it("is announced as an alert so it is not a silent empty region", () => {
    render(<LoadError error={axiosErrorWith(500, {})} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("offers a retry when one is given, and omits it otherwise", async () => {
    const retry = vi.fn();
    const { unmount } = render(<LoadError error={axiosErrorWith(503, {})} retry={retry} />);
    await userEvent.click(screen.getByRole("button", { name: "再試行" }));
    expect(retry).toHaveBeenCalledOnce();
    unmount();
    render(<LoadError error={axiosErrorWith(503, {})} />);
    expect(screen.queryByRole("button", { name: "再試行" })).toBeNull();
  });
});
