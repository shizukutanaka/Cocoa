import { lazy, Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./hooks/useAuth";
import { ToastProvider } from "./hooks/useToast";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/Layout";
import { RequireAuth } from "./components/RequireAuth";
import { MyPageLayout } from "./components/MyPageLayout";
import { CenterSpinner } from "./components/Spinner";

// Route-level code splitting: each page becomes its own chunk so the initial
// load only ships the marketplace landing, not every authenticated screen.
const Marketplace = lazy(() => import("./pages/Marketplace").then((m) => ({ default: m.Marketplace })));
const Bundles = lazy(() => import("./pages/Bundles").then((m) => ({ default: m.Bundles })));
const ListingDetail = lazy(() => import("./pages/ListingDetail").then((m) => ({ default: m.ListingDetail })));
const Login = lazy(() => import("./pages/Login").then((m) => ({ default: m.Login })));
const Register = lazy(() => import("./pages/Register").then((m) => ({ default: m.Register })));
const CartPage = lazy(() => import("./pages/Cart").then((m) => ({ default: m.CartPage })));
const Collections = lazy(() => import("./pages/Collections").then((m) => ({ default: m.Collections })));
const CollectionDetail = lazy(() => import("./pages/CollectionDetail").then((m) => ({ default: m.CollectionDetail })));
const Profile = lazy(() => import("./pages/me/Profile").then((m) => ({ default: m.Profile })));
const Orders = lazy(() => import("./pages/me/Orders").then((m) => ({ default: m.Orders })));
const OrderDetail = lazy(() => import("./pages/me/OrderDetail").then((m) => ({ default: m.OrderDetail })));
const Credits = lazy(() => import("./pages/me/Credits").then((m) => ({ default: m.Credits })));
const GiftCards = lazy(() => import("./pages/me/GiftCards").then((m) => ({ default: m.GiftCards })));
const Notifications = lazy(() => import("./pages/me/Notifications").then((m) => ({ default: m.Notifications })));
const Security = lazy(() => import("./pages/me/Security").then((m) => ({ default: m.Security })));
const MyListings = lazy(() => import("./pages/me/MyListings").then((m) => ({ default: m.MyListings })));
const CreateListing = lazy(() => import("./pages/me/CreateListing").then((m) => ({ default: m.CreateListing })));
const Wishlist = lazy(() => import("./pages/me/Wishlist").then((m) => ({ default: m.Wishlist })));
const SavedSearches = lazy(() => import("./pages/me/SavedSearches").then((m) => ({ default: m.SavedSearches })));
const Referrals = lazy(() => import("./pages/me/Referrals").then((m) => ({ default: m.Referrals })));
const Creator = lazy(() => import("./pages/Creator").then((m) => ({ default: m.Creator })));
const Following = lazy(() => import("./pages/me/Following").then((m) => ({ default: m.Following })));
const PromoCodes = lazy(() => import("./pages/me/PromoCodes").then((m) => ({ default: m.PromoCodes })));
const Licenses = lazy(() => import("./pages/me/Licenses").then((m) => ({ default: m.Licenses })));
const ListingLicenses = lazy(() => import("./pages/me/ListingLicenses").then((m) => ({ default: m.ListingLicenses })));
const Tips = lazy(() => import("./pages/me/Tips").then((m) => ({ default: m.Tips })));
const Refunds = lazy(() => import("./pages/me/Refunds").then((m) => ({ default: m.Refunds })));
const MyBundles = lazy(() => import("./pages/me/Bundles").then((m) => ({ default: m.Bundles })));
const Commissions = lazy(() => import("./pages/me/Commissions").then((m) => ({ default: m.Commissions })));
const CreatorDashboard = lazy(() => import("./pages/me/CreatorDashboard").then((m) => ({ default: m.CreatorDashboard })));
const Feed = lazy(() => import("./pages/me/Feed").then((m) => ({ default: m.Feed })));

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
              <Suspense fallback={<CenterSpinner />}>
                <Routes>
                  <Route element={<Layout />}>
                    <Route index element={<Marketplace />} />
                    <Route path="listings/:listingId" element={<ListingDetail />} />
                    <Route path="users/:userId" element={<Creator />} />
                    <Route path="bundles" element={<Bundles />} />
                    <Route path="login" element={<Login />} />
                    <Route path="register" element={<Register />} />

                    <Route path="cart" element={<RequireAuth><CartPage /></RequireAuth>} />
                    <Route path="collections" element={<RequireAuth><Collections /></RequireAuth>} />
                    <Route path="collections/:collectionId" element={<RequireAuth><CollectionDetail /></RequireAuth>} />

                    <Route path="me" element={<RequireAuth><MyPageLayout /></RequireAuth>}>
                      <Route index element={<Profile />} />
                      <Route path="listings" element={<MyListings />} />
                      <Route path="listings/new" element={<CreateListing />} />
                      <Route path="promo-codes" element={<PromoCodes />} />
                      <Route path="licenses" element={<Licenses />} />
                      <Route path="listings/:listingId/licenses" element={<ListingLicenses />} />
                      <Route path="tips" element={<Tips />} />
                      <Route path="refunds" element={<Refunds />} />
                      <Route path="bundles" element={<MyBundles />} />
                      <Route path="commissions" element={<Commissions />} />
                      <Route path="dashboard" element={<CreatorDashboard />} />
                      <Route path="feed" element={<Feed />} />
                      <Route path="wishlist" element={<Wishlist />} />
                      <Route path="saved-searches" element={<SavedSearches />} />
                      <Route path="referrals" element={<Referrals />} />
                      <Route path="following" element={<Following />} />
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
              </Suspense>
            </ToastProvider>
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
