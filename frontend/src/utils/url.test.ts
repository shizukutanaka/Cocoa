import { describe, it, expect } from "vitest";
import { isSafeHttpUrl } from "./url";

/**
 * This is the render-site half of the stored-XSS fix (FEATURE_AUDIT.md #35):
 * profile URLs are attacker-controlled and are rendered as <a href> / <img src>
 * on a public page, so a javascript: URI surviving to render executes in a
 * visitor's browser -- including an admin's.
 */
describe("isSafeHttpUrl", () => {
  it.each([
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "  javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
  ])("rejects the dangerous scheme %s", (raw) => {
    expect(isSafeHttpUrl(raw)).toBe(false);
  });

  it.each([
    "http://example.com",
    "https://example.com/path?q=1#frag",
    "https://example.com:8443/a",
  ])("allows the http(s) URL %s", (raw) => {
    expect(isSafeHttpUrl(raw)).toBe(true);
  });

  it.each([null, undefined, "", "   ", "not a url", "//example.com", "example.com"])(
    "rejects the non-URL value %s",
    (raw) => {
      expect(isSafeHttpUrl(raw)).toBe(false);
    },
  );
});
