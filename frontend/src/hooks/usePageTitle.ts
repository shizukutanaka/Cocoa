import { useEffect } from "react";

const BASE = "Cocoa";

// Sets document.title for the mounted page and restores the base title on
// unmount. SPA route changes never reload index.html, so without this every
// page would keep the initial <title>, hurting orientation and a11y.
export function usePageTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${title} · ${BASE}` : BASE;
    return () => {
      document.title = BASE;
    };
  }, [title]);
}
