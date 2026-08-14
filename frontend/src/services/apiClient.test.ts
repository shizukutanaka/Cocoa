import { describe, it, expect } from "vitest";
import { AxiosError, AxiosHeaders } from "axios";
import { apiErrorMessage } from "./apiClient";

function axiosErrorWith(status: number, data: unknown): AxiosError {
  const config = { headers: new AxiosHeaders() };
  const err = new AxiosError("request failed", "ERR_BAD_RESPONSE", config);
  err.response = {
    status,
    statusText: "",
    data,
    headers: {},
    config,
  } as AxiosError["response"];
  return err;
}

describe("apiErrorMessage", () => {
  it("surfaces the backend's detail message", () => {
    const err = axiosErrorWith(400, { detail: "購入済みのリスティングのみレビューできます" });
    expect(apiErrorMessage(err)).toBe("購入済みのリスティングのみレビューできます");
  });

  it("explains a 503 as a temporary outage rather than the generic fallback", () => {
    // Since FEATURE_AUDIT.md #47 an unavailable subsystem answers 503 instead
    // of an empty 200, so this is the message users actually see in an outage.
    const err = axiosErrorWith(503, {});
    expect(apiErrorMessage(err)).toBe("サービスが一時的に利用できません");
  });

  it("prefers the detail over the 503 default when both are present", () => {
    const err = axiosErrorWith(503, { detail: "マーケットプレイスが利用できません" });
    expect(apiErrorMessage(err)).toBe("マーケットプレイスが利用できません");
  });

  it("falls back for a non-axios error", () => {
    expect(apiErrorMessage(new Error("boom"), "取得に失敗しました")).toBe("取得に失敗しました");
  });

  it("uses the caller's fallback when the response carries no detail", () => {
    const err = axiosErrorWith(500, {});
    expect(apiErrorMessage(err, "更新に失敗しました")).toBe("更新に失敗しました");
  });
});
