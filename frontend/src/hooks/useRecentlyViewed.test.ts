import { describe, it, expect, beforeEach } from "vitest";
import { recordRecentlyViewed, getRecentlyViewed } from "./useRecentlyViewed";

describe("recentlyViewed", () => {
  beforeEach(() => localStorage.clear());

  it("starts empty", () => {
    expect(getRecentlyViewed()).toEqual([]);
  });

  it("records most-recent first", () => {
    recordRecentlyViewed("a");
    recordRecentlyViewed("b");
    expect(getRecentlyViewed()).toEqual(["b", "a"]);
  });

  it("dedupes and moves a re-viewed listing to the front", () => {
    recordRecentlyViewed("a");
    recordRecentlyViewed("b");
    recordRecentlyViewed("a");
    expect(getRecentlyViewed()).toEqual(["a", "b"]);
  });

  it("caps the history at 12 entries", () => {
    for (let i = 0; i < 20; i++) recordRecentlyViewed(`id${i}`);
    const ids = getRecentlyViewed();
    expect(ids).toHaveLength(12);
    // The 12 most recent, newest first.
    expect(ids[0]).toBe("id19");
    expect(ids).not.toContain("id7");
  });

  it("ignores an empty id", () => {
    recordRecentlyViewed("");
    expect(getRecentlyViewed()).toEqual([]);
  });

  it("returns empty on a corrupt stored value instead of throwing", () => {
    localStorage.setItem("cocoa:recently-viewed", "{not json");
    expect(getRecentlyViewed()).toEqual([]);
  });
});
