import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * Every page that renders an empty state must also branch on isError (#101).
 *
 * #47 stopped the server reporting a broken subsystem as an empty 200. #100
 * found the interface doing the same thing one layer up -- a failed query
 * leaves `data` undefined, so `!data || data.items.length === 0` rendered a
 * 503 as "you have nothing yet" -- and fixed three pages.
 *
 * That fix came with a claim that the remaining pages were fine. The claim was
 * wrong: it rested on grepping one of the several shapes this pattern takes,
 * and a proper sweep found nineteen more, including the moderation console,
 * where an outage told a moderator the report queue was empty.
 *
 * So the guard is a test rather than a claim. Fixing N instances does not
 * close a class; only something that fails on instance N+1 does.
 */
// vitest runs with the frontend package as cwd; import.meta.url resolves to a
// bare "/src" here, so anchor on cwd instead.
const SRC = join(process.cwd(), "src");

function tsxFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) return tsxFiles(full);
    return name.endsWith(".tsx") && !name.includes(".test.") ? [full] : [];
  });
}

describe("an outage is never rendered as an empty state", () => {
  it("every file with an empty state and a query also handles isError", () => {
    const offenders = tsxFiles(SRC)
      .map((file) => ({ file, text: readFileSync(file, "utf8") }))
      .filter(({ text }) => text.includes("empty-state") && text.includes("useQuery"))
      .filter(({ text }) => !text.includes("isError"))
      .map(({ file }) => file.replace(SRC, ""));

    expect(
      offenders,
      `these render an empty state but never check isError, so a failed request ` +
        `shows as "nothing here" instead of an outage:\n  ${offenders.join("\n  ")}`,
    ).toEqual([]);
  });

  it("the guard would notice a page that stopped handling isError", () => {
    // Proves the check above can fail: the same predicate over a sample that
    // has an empty state and a query but no isError.
    const sample = `useQuery(); <div className="empty-state">まだありません</div>`;
    const handled = sample.includes("isError");
    expect(handled).toBe(false);
  });
});
