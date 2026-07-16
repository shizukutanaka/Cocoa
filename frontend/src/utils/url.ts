// Defense-in-depth check for user-controlled URLs (profile website_url,
// avatar_url, social_links) before rendering them as <a href>/<img src>.
// The backend already rejects non-http(s) schemes at write time
// (main/auth_manager.py _sanitize_public_url), but any accepted value should
// still be validated once more at the render site so a future write path
// that skips server-side validation can't reintroduce a javascript: URI XSS.
export function isSafeHttpUrl(raw: string | null | undefined): boolean {
  if (!raw) return false;
  try {
    const url = new URL(raw);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}
