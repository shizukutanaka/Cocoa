import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useDebouncedValue } from "./useDebouncedValue";

describe("useDebouncedValue", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("returns the initial value immediately", () => {
    const { result } = renderHook(() => useDebouncedValue("a", 250));
    expect(result.current).toBe("a");
  });

  it("holds the old value until the delay elapses", () => {
    const { result, rerender } = renderHook(({ v }) => useDebouncedValue(v, 250), {
      initialProps: { v: "a" },
    });
    rerender({ v: "b" });
    expect(result.current).toBe("a");

    act(() => void vi.advanceTimersByTime(249));
    expect(result.current).toBe("a");

    act(() => void vi.advanceTimersByTime(1));
    expect(result.current).toBe("b");
  });

  it("emits only the final value when typing quickly", () => {
    // The point of the hook: one suggest request on a pause, not one per
    // keystroke.
    const { result, rerender } = renderHook(({ v }) => useDebouncedValue(v, 250), {
      initialProps: { v: "" },
    });
    for (const v of ["a", "av", "ava", "avat"]) {
      rerender({ v });
      act(() => void vi.advanceTimersByTime(100));
    }
    expect(result.current).toBe("");

    act(() => void vi.advanceTimersByTime(250));
    expect(result.current).toBe("avat");
  });
});
