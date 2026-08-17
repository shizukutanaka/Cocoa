// Client-side "recently viewed listings", stored in localStorage. A standard
// marketplace affordance (Booth / Gumroad / Amazon) that needs no backend: the
// browsing history is personal to the device and never leaves it.
const KEY = "cocoa:recently-viewed";
const MAX = 12;

function read(): string[] {
  try {
    const raw = localStorage.getItem(KEY);
    const ids = raw ? JSON.parse(raw) : [];
    return Array.isArray(ids) ? ids.filter((x): x is string => typeof x === "string") : [];
  } catch {
    // Corrupt value or storage disabled (private mode) -> behave as empty.
    return [];
  }
}

/** Record a listing as most-recently viewed: moves it to the front, dedupes,
 * and caps the list. Safe to call repeatedly. */
export function recordRecentlyViewed(listingId: string): void {
  if (!listingId) return;
  try {
    const next = [listingId, ...read().filter((id) => id !== listingId)].slice(0, MAX);
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // Quota / disabled storage: recently-viewed is a nicety, never surface it.
  }
}

/** The recorded ids, most-recent first. Read once (localStorage isn't
 * reactive), which is fine for a landing-page strip rendered on mount. */
export function getRecentlyViewed(): string[] {
  return read();
}
