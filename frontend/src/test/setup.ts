// Registers @testing-library/jest-dom matchers (toBeInTheDocument, toBeDisabled,
// ...) with Vitest's expect. Living under src/ means tsc --noEmit also picks up
// the matcher type augmentation, so no tsconfig "types" entry is needed.
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Testing Library only auto-registers its cleanup when Vitest globals are on.
// We deliberately keep globals off (so ESLint and tsc need no extra config),
// so unmount between tests explicitly -- otherwise rendered trees accumulate
// and queries match elements left over from earlier tests.
afterEach(cleanup);
