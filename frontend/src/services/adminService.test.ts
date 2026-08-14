import { describe, it, expect } from "vitest";
import { REASON_SEVERITY, SEVERITY_LABEL, severityOf } from "./adminService";

/**
 * Moderation triage order (FEATURE_AUDIT.md #46): the queue is sorted by these
 * numbers so the highest-risk reports are actioned first instead of whatever
 * arrived first. Silently reordering them would change what a moderator sees
 * at the top of the queue, so the ordering is pinned here.
 */
describe("severityOf", () => {
  it("ranks malware and copyright above taste-level complaints", () => {
    expect(severityOf("malware")).toBeLessThan(severityOf("spam"));
    expect(severityOf("copyright")).toBeLessThan(severityOf("spam"));
    expect(severityOf("malware")).toBeLessThan(severityOf("other"));
  });

  it("puts malware first overall", () => {
    const worst = Math.min(...Object.keys(REASON_SEVERITY).map(severityOf));
    expect(severityOf("malware")).toBe(worst);
  });

  it("orders the full listing-report scale from most to least severe", () => {
    const order = ["malware", "copyright", "inappropriate", "misleading", "spam", "other"];
    const ranks = order.map(severityOf);
    expect(ranks).toEqual([...ranks].sort((a, b) => a - b));
  });

  it("treats an unknown reason as lowest priority instead of highest", () => {
    // Defaulting an unrecognised reason to 0 would let a typo jump the queue.
    expect(severityOf("brand-new-reason")).toBe(5);
    expect(severityOf("")).toBe(5);
  });

  it("has a label for every severity level it can return", () => {
    for (const reason of Object.keys(REASON_SEVERITY)) {
      expect(SEVERITY_LABEL[severityOf(reason)]).toBeTruthy();
    }
    expect(SEVERITY_LABEL[severityOf("unknown")]).toBeTruthy();
  });
});
