// Types mirror main/api_server.py response shapes exactly (field names/casing)
// -- see each dataclass's to_dict() in main/*.py for the source of truth.

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface PendingTwoFactor {
  requires_2fa: true;
  pending_token: string;
  expires_in: number;
}

export type LoginResult = TokenPair | PendingTwoFactor;

export interface CurrentUser {
  user_id: string;
  username: string;
  role: string;
  email?: string;
  display_name?: string;
  bio?: string;
  avatar_url?: string;
  is_email_verified?: boolean;
}

export interface Listing {
  listing_id: string;
  avatar_id: string;
  owner_id: string;
  owner_username: string;
  name: string;
  description: string;
  tags: string[];
  category: string;
  platform: string;
  thumbnail_url: string;
  is_free: boolean;
  price_credits: number;
  license_type: string;
  license_details: string;
  download_count: number;
  average_rating: number;
  rating_count: number;
  current_version: number;
  published_at: string;
  updated_at: string;
  stock_limit: number | null;
  stock_remaining: number | null;
  is_sold_out: boolean;
  is_active: boolean;
  is_ai_generated: boolean;
  // Parameter VALUES stay hidden until purchase; only the count and a small
  // sample of key NAMES are exposed so shoppers can gauge an avatar's richness.
  parameter_count: number;
  parameter_keys_preview: string[];
}

export interface Paginated<T> {
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
  next_offset: number | null;
  items: T[];
  facets?: {
    categories: Record<string, number>;
    license_types: Record<string, number>;
    top_tags: Record<string, number>;
    platforms: Record<string, number>;
  };
}

export interface CartItem {
  listing_id: string;
  name: string;
  owner_id: string;
  owner_username: string;
  price_credits: number;
  is_free: boolean;
  promo_code: string;
  quantity: number;
  added_at: string;
}

export interface Cart {
  cart_id: string;
  user_id: string;
  items: CartItem[];
  item_count: number;
  subtotal_credits: number;
  created_at: string;
  updated_at: string;
}

export interface OrderItem {
  listing_id: string;
  name: string;
  owner_id: string;
  owner_username: string;
  unit_price: number;
  final_price: number;
  quantity: number;
  promo_code: string;
  discount_percent: number;
}

export interface Order {
  order_id: string;
  user_id: string;
  items: OrderItem[];
  total_credits: number;
  status: string;
  failure_reason?: string;
  created_at: string;
}

export interface CheckoutResult {
  order: Order;
  failed_items: Array<{ listing_id: string; reason: string }>;
  success: boolean;
  listings_deactivated?: number;
  collections_deleted?: number;
}

export interface Collection {
  collection_id: string;
  owner_id: string;
  name: string;
  description: string;
  is_public: boolean;
  item_ids: string[];
  item_count: number;
  created_at: string;
  updated_at: string;
}

export interface CollectionItemStatus {
  listing_id: string;
  is_active: boolean;
  is_sold_out: boolean;
  is_available: boolean;
  delisted: boolean;
  current_price: number | null;
  listing_name: string | null;
  owner_id: string | null;
}

export interface Notification {
  notification_id: string;
  kind: string;
  title: string;
  body: string;
  payload: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
}

export interface NotificationsResponse {
  total: number;
  offset: number;
  unread_count: number;
  items: Notification[];
}

export interface CreditHistoryEntry {
  amount: number;
  kind: string;
  ref_id: string;
  balance_after: number;
  ts: string;
}

export interface TwoFactorSetupData {
  secret: string;
  qr_code_uri?: string;
  qr_code_image?: string | null; // "data:image/png;base64,..." -- drop straight into <img src>; null if the qrcode package isn't installed server-side
  backup_codes: string[];
}

export interface TwoFactorStatus {
  is_enabled: boolean;
  backup_codes_remaining?: number;
}

export interface ApiErrorBody {
  detail?: string;
  error_code?: number;
}

export interface Review {
  review_id: string;
  listing_id: string;
  user_id: string;
  username: string;
  stars: number;
  text: string;
  helpful_count: number;
  unhelpful_count: number;
  is_hidden: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReviewsResponse {
  total: number;
  items: Review[];
}

// Mirrors main/avatar_marketplace.py ReviewReply.to_dict()
export interface ReviewReply {
  reply_id: string;
  review_id: string;
  user_id: string;
  username: string;
  text: string;
  created_at: string;
}

export interface GiftCard {
  card_id: string;
  code: string;
  purchaser_id?: string; // omitted from the redeemer-facing to_public_dict()
  amount: number;
  is_redeemed: boolean;
  redeemed_by: string | null;
  message: string;
  expires_at: string | null;
  is_valid: boolean;
  created_at: string;
  redeemed_at: string | null;
}

export interface GiftCardRedeemResult {
  card: GiftCard;
  credits_received: number;
  new_balance: number;
}

export interface WishlistItem {
  listing_id: string;
  snapshot_price: number;
  snapshot_name: string;
  added_at: string;
  // Only present when fetched with with_status=true.
  is_active?: boolean;
  is_sold_out?: boolean;
  is_available?: boolean;
  delisted?: boolean;
  current_price?: number | null;
  price_changed?: boolean;
  price_dropped?: boolean;
}

export interface PublishListingInput {
  avatar_id: string;
  name: string;
  description?: string;
  tags?: string[];
  category?: string;
  platform?: string;
  parameters?: Record<string, unknown>;
  thumbnail_url?: string;
  is_free?: boolean;
  price_credits?: number;
  license_type?: string;
  license_details?: string;
  is_ai_generated?: boolean;
}

export interface UpdateListingInput {
  name?: string;
  description?: string;
  tags?: string[];
  parameters?: Record<string, unknown>;
  thumbnail_url?: string;
  is_free?: boolean;
  price_credits?: number;
  license_type?: string;
  license_details?: string;
  platform?: string;
  is_ai_generated?: boolean;
}

// Mirrors main/auth_manager.py CreatorApplication.to_dict()
export interface CreatorApplication {
  application_id: string;
  user_id: string;
  username: string;
  reason: string;
  portfolio_url: string;
  status: "pending" | "approved" | "rejected";
  reviewed_by: string;
  review_note: string;
  created_at: string;
  reviewed_at: string | null;
}

// Mirrors main/avatar_marketplace.py MarketplaceStore.get_creator_analytics()
export interface CreatorAnalytics {
  owner_id: string;
  total_listings: number;
  active_listings: number;
  total_downloads: number;
  total_reviews: number;
  total_credits_earned: number;
  rating_distribution: Record<string, number>;
  downloads_by_day: Record<string, number>;
  downloads_by_tag: Record<string, number>;
  downloads_by_category: Record<string, number>;
  top_listing: Listing | null;
}

// Mirrors main/avatar_marketplace.py MarketplaceStore.get_earnings_summary()
export interface EarningsSummary {
  user_id: string;
  period_days: number;
  total_earned: number;
  sales: number;
  tips_and_gifts_received: number;
  by_day: Record<string, number>;
}

// Mirrors main/auth_manager.py AuthStore.create_api_key()/list_api_keys() entries
export interface ApiKey {
  key_id: string;
  user_id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used: string | null;
  raw_key?: string; // only present in the create response, shown once
}

// Mirrors main/membership_manager.py MembershipRecord.to_dict()
export interface Membership {
  user_id: string;
  lifetime_credits: number;
  tier: "bronze" | "silver" | "gold" | "diamond";
  tier_label: string;
  fee_discount_percent: number;
  next_tier_threshold: number | null;
  credits_to_next_tier: number | null;
  updated_at: string;
}

// Mirrors the dicts appended in MarketplaceStore.publish()/update_listing()
export interface PriceHistoryEntry {
  price_credits: number;
  is_free: boolean;
  changed_at: string;
}

// Mirrors main/commissions.py CommissionRequest.to_dict()
export interface CommissionRequest {
  request_id: string;
  requester_id: string;
  requester_username: string;
  creator_id: string;
  title: string;
  description: string;
  budget_credits: number;
  status: "pending" | "accepted" | "declined" | "delivered" | "closed";
  creator_note: string;
  delivery_note: string;
  delivery_listing_id: string;
  created_at: string;
  updated_at: string;
}

// Mirrors main/bundle_manager.py Bundle.to_dict()
export interface Bundle {
  bundle_id: string;
  creator_id: string;
  creator_username: string;
  name: string;
  description: string;
  listing_ids: string[];
  listing_count: number;
  discount_percent: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// BundleManager.purchase_bundle() receipt
export interface BundlePurchaseResult {
  bundle_id: string;
  buyer_id: string;
  discount_percent: number;
  purchased: Array<{
    listing_id: string;
    name: string;
    owner_id: string;
    owner_username: string;
    unit_price: number;
    final_price: number;
    discount_percent: number;
  }>;
  skipped: Array<{ listing_id: string; reason: string }>;
  total_charged: number;
  order_id: string | null;
}

// Mirrors main/refund_manager.py RefundRequest.to_dict()
export interface RefundRequestRecord {
  request_id: string;
  order_id: string;
  user_id: string;
  total_credits: number;
  reason: string;
  status: "pending" | "approved" | "rejected";
  admin_notes: string;
  resolved_by: string;
  created_at: string;
  resolved_at: string | null;
}

// Mirrors main/avatar_marketplace.py Tip.to_dict() / to_public_dict()
export interface Tip {
  tip_id: string;
  sender_id?: string; // omitted from the public view (GET /api/users/{id}/tips)
  sender_username: string;
  recipient_id?: string;
  amount: number;
  message?: string; // omitted from the public view
  created_at: string;
}

// Mirrors main/license_manager.py LicenseActivation.to_dict()
export interface LicenseActivation {
  activation_id: string;
  note: string;
  activated_at: string;
}

// Mirrors main/license_manager.py LicenseKey.to_dict()
export interface LicenseKey {
  key_id: string;
  key: string;
  listing_id: string;
  owner_id: string;
  holder_id: string;
  max_activations: number | null;
  activation_count: number;
  is_revoked: boolean;
  revoked_by: string;
  revoked_reason: string;
  activations: LicenseActivation[];
  issued_at: string;
  revoked_at: string | null;
}

// Mirrors main/avatar_marketplace.py PromoCode.to_dict()
export interface PromoCode {
  code_id: string;
  code: string;
  creator_id: string;
  discount_percent: number;
  listing_id: string | null;
  max_uses: number | null;
  uses_count: number;
  expires_at: string | null;
  is_active: boolean;
  is_valid: boolean;
  created_at: string;
}

// GET /api/marketplace/{listing_id}/promo/{code} (lookup_promo_code)
export interface PromoLookup {
  code: string;
  discount_percent: number;
  original_price: number;
  discounted_price: number;
  listing_id: string;
}

// Mirrors main/auth_manager.py User.public_profile() (+followers_count where
// the endpoint adds it, e.g. /api/users/{id}/profile and storefront.profile)
export interface PublicProfile {
  user_id: string;
  username: string;
  display_name: string;
  bio: string;
  avatar_url: string;
  website_url: string;
  social_links: Record<string, string>;
  role: string;
  is_email_verified: boolean;
  is_creator_verified: boolean;
  created_at: string;
  followers_count?: number;
}

export interface Storefront {
  profile: PublicProfile;
  listings: Paginated<Listing>;
  // Creator dashboard stats (main/avatar_marketplace.py get_creator_analytics);
  // only the fields the storefront page actually renders are typed here.
  analytics: {
    total_downloads?: number;
    active_listings?: number;
    total_reviews?: number;
  } | null;
}

// Mirrors main/referral_manager.py ReferralRecord.to_dict()
export interface ReferralRecord {
  referral_id: string;
  referrer_id: string;
  referred_id: string;
  referral_code: string;
  status: "pending" | "converted";
  bonus_awarded: number;
  created_at: string;
  converted_at: string | null;
}

// Mirrors ReferralStore.get_referral_stats()
export interface ReferralStats {
  referrer_id: string;
  total_referrals: number;
  converted: number;
  pending: number;
  total_bonus_earned: number;
}

// Mirrors main/saved_searches.py SavedSearch.to_dict()
export interface SavedSearchFilters {
  category?: string;
  platform?: string;
  tags?: string[];
  sort_by?: string;
  is_free?: boolean;
  min_price?: number;
  max_price?: number;
}

export interface SavedSearch {
  search_id: string;
  user_id: string;
  name: string;
  query: string;
  filters: SavedSearchFilters;
  notify_on_match: boolean;
  created_at: string;
  last_used: string | null;
  use_count: number;
}
