import type { ReactElement, ReactNode } from "react";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../hooks/useAuth";
import { ToastProvider } from "../hooks/useToast";

/**
 * Renders a component inside the same provider nesting App.tsx uses, so tests
 * exercise components the way the running app composes them rather than in
 * isolation. MemoryRouter takes initialEntries, which is how a test reproduces
 * an emailed link such as /verify-email?token=abc.
 */
export function renderWithProviders(
  ui: ReactElement,
  { initialEntries = ["/"] }: { initialEntries?: string[] } = {},
) {
  // A fresh client per test keeps cached queries from leaking between tests;
  // retry is off so a rejected query surfaces immediately.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={initialEntries}>
          <AuthProvider>
            <ToastProvider>{children}</ToastProvider>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  return render(ui, { wrapper: Wrapper });
}
