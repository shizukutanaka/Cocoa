import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./hooks/useAuth";
import { ToastProvider } from "./hooks/useToast";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/Layout";
import { RequireAuth } from "./components/RequireAuth";
import { MyPageLayout } from "./components/MyPageLayout";
import { Marketplace } from "./pages/Marketplace";
import { ListingDetail } from "./pages/ListingDetail";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { CartPage } from "./pages/Cart";
import { Collections } from "./pages/Collections";
import { CollectionDetail } from "./pages/CollectionDetail";
import { Profile } from "./pages/me/Profile";
import { Orders } from "./pages/me/Orders";
import { OrderDetail } from "./pages/me/OrderDetail";
import { Credits } from "./pages/me/Credits";
import { GiftCards } from "./pages/me/GiftCards";
import { Notifications } from "./pages/me/Notifications";
import { Security } from "./pages/me/Security";
import { MyListings } from "./pages/me/MyListings";
import { CreateListing } from "./pages/me/CreateListing";
import { Wishlist } from "./pages/me/Wishlist";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <ToastProvider>
              <Routes>
                <Route element={<Layout />}>
                  <Route index element={<Marketplace />} />
                  <Route path="listings/:listingId" element={<ListingDetail />} />
                  <Route path="login" element={<Login />} />
                  <Route path="register" element={<Register />} />

                  <Route path="cart" element={<RequireAuth><CartPage /></RequireAuth>} />
                  <Route path="collections" element={<RequireAuth><Collections /></RequireAuth>} />
                  <Route path="collections/:collectionId" element={<RequireAuth><CollectionDetail /></RequireAuth>} />

                  <Route path="me" element={<RequireAuth><MyPageLayout /></RequireAuth>}>
                    <Route index element={<Profile />} />
                    <Route path="listings" element={<MyListings />} />
                    <Route path="listings/new" element={<CreateListing />} />
                    <Route path="wishlist" element={<Wishlist />} />
                    <Route path="orders" element={<Orders />} />
                    <Route path="orders/:orderId" element={<OrderDetail />} />
                    <Route path="credits" element={<Credits />} />
                    <Route path="gift-cards" element={<GiftCards />} />
                    <Route path="notifications" element={<Notifications />} />
                    <Route path="security" element={<Security />} />
                  </Route>

                  <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
              </Routes>
            </ToastProvider>
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
