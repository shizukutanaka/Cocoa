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
