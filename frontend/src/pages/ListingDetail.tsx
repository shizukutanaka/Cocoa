import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import * as marketplaceService from "../services/marketplaceService";
import { getListing } from "../services/marketplaceService";
import { addToCart } from "../services/cartService";
import * as wishlistService from "../services/wishlistService";
import { CenterSpinner } from "../components/Spinner";
import { StarRating } from "../components/StarRating";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { apiErrorMessage } from "../services/apiClient";

export function ListingDetail() {
  const { listingId } = useParams<{ listingId: string }>();
  const { user } = useAuth();
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [addingToCart, setAddingToCart] = useState(false);

  const { data: listing, isLoading, isError } = useQuery({
    queryKey: ["listing", listingId],
    queryFn: () => getListing(listingId!),
    enabled: !!listingId,
  });

  const { data: inWishlist } = useQuery({
    queryKey: ["wishlist-check", listingId],
    queryFn: () => wishlistService.checkWishlist(listingId!),
    enabled: !!listingId && !!user,
  });

  async function handleAddToCart() {
    if (!listing) return;
    setAddingToCart(true);
    try {
      await addToCart(listing.listing_id);
      queryClient.invalidateQueries({ queryKey: ["cart"] });
      show("カートに追加しました");
    } catch (err) {
      show(apiErrorMessage(err, "カートへの追加に失敗しました"), "error");
    } finally {
      setAddingToCart(false);
    }
  }

  async function handleToggleWishlist() {
    if (!listing) return;
    try {
      if (inWishlist) {
        await wishlistService.removeFromWishlist(listing.listing_id);
        show("ウィッシュリストから削除しました");
      } else {
        await wishlistService.addToWishlist(listing.listing_id);
        show("ウィッシュリストに追加しました");
      }
      queryClient.invalidateQueries({ queryKey: ["wishlist-check", listingId] });
    } catch (err) {
      show(apiErrorMessage(err, "ウィッシュリストの更新に失敗しました"), "error");
    }
  }

  if (isLoading) return <CenterSpinner />;
  if (isError || !listing) return <div className="empty-state">リスティングが見つかりませんでした。</div>;

  const isOwnListing = user?.user_id === listing.owner_id;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 }}>
      <div className="card listing-thumb" style={{ aspectRatio: "1", borderRadius: "var(--radius)" }}>
        {listing.thumbnail_url ? <img src={listing.thumbnail_url} alt="" /> : "No Image"}
      </div>

      <div>
        <h1>{listing.name}</h1>
        <p style={{ color: "var(--muted)" }}>
          by {listing.owner_username} · {listing.platform || "汎用"}
        </p>

        <div style={{ display: "flex", gap: 8, margin: "12px 0" }}>
          {listing.tags.map((tag) => (
            <span key={tag} className="badge">
              {tag}
            </span>
          ))}
        </div>

        <p>{listing.description}</p>

        <div className="stat-row">
          <div className="stat-tile">
            <div className="stat-value">{listing.is_free ? "無料" : `${listing.price_credits.toLocaleString()} cr`}</div>
            <div className="stat-label">価格</div>
          </div>
          <div className="stat-tile">
            <div className="stat-value">
              {listing.rating_count > 0 ? listing.average_rating.toFixed(1) : "-"}
            </div>
            <div className="stat-label">評価（{listing.rating_count}件）</div>
          </div>
          <div className="stat-tile">
            <div className="stat-value">{listing.download_count.toLocaleString()}</div>
            <div className="stat-label">ダウンロード数</div>
          </div>
        </div>

        {listing.is_sold_out && <div className="form-error-banner">在庫切れです</div>}

        {!isOwnListing && (
          <div style={{ display: "flex", gap: 8 }}>
            {!listing.is_sold_out && (
              <button className="btn btn-primary" onClick={handleAddToCart} disabled={addingToCart}>
                {addingToCart ? "追加中..." : "カートに追加"}
              </button>
            )}
            {user && (
              <button className="btn btn-secondary" onClick={handleToggleWishlist}>
                {inWishlist ? "★ ウィッシュリスト済み" : "☆ ウィッシュリストに追加"}
              </button>
            )}
          </div>
        )}
        {isOwnListing && <p style={{ color: "var(--muted)" }}>これはあなたが出品したリスティングです。</p>}
      </div>

      <div style={{ gridColumn: "1 / -1" }}>
        <ReviewsSection listingId={listing.listing_id} isOwnListing={isOwnListing} isLoggedIn={!!user} />
      </div>
    </div>
  );
}

function ReviewsSection({
  listingId,
  isOwnListing,
  isLoggedIn,
}: {
  listingId: string;
  isOwnListing: boolean;
  isLoggedIn: boolean;
}) {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [stars, setStars] = useState(5);
  const [text, setText] = useState("");
  const [posting, setPosting] = useState(false);

  const { data: reviews, isLoading } = useQuery({
    queryKey: ["reviews", listingId],
    queryFn: () => marketplaceService.listReviews(listingId),
  });

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setPosting(true);
    try {
      await marketplaceService.postReview(listingId, stars, text);
      setText("");
      queryClient.invalidateQueries({ queryKey: ["reviews", listingId] });
      queryClient.invalidateQueries({ queryKey: ["listing", listingId] });
      show("レビューを投稿しました");
    } catch (err) {
      show(apiErrorMessage(err, "レビューの投稿に失敗しました"), "error");
    } finally {
      setPosting(false);
    }
  }

  async function handleHelpful(reviewId: string, helpful: boolean) {
    try {
      await marketplaceService.voteReviewHelpful(reviewId, helpful);
      queryClient.invalidateQueries({ queryKey: ["reviews", listingId] });
    } catch (err) {
      show(apiErrorMessage(err, "投票に失敗しました"), "error");
    }
  }

  return (
    <section style={{ marginTop: 12 }}>
      <h2 style={{ fontSize: 18 }}>レビュー</h2>

      {isLoggedIn && !isOwnListing && (
        <form onSubmit={handleSubmit} className="card card-pad" style={{ maxWidth: 480, marginBottom: 20 }}>
          <div className="field">
            <label>評価</label>
            <div style={{ marginTop: 4 }}>
              <StarRating value={stars} onChange={setStars} size={22} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="review-text">コメント（任意）</label>
            <textarea id="review-text" value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={2000} />
          </div>
          <button type="submit" className="btn btn-primary" disabled={posting}>
            {posting ? "投稿中..." : "レビューを投稿"}
          </button>
        </form>
      )}

      {isLoading ? (
        <CenterSpinner />
      ) : !reviews || reviews.items.length === 0 ? (
        <div className="empty-state">まだレビューがありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {reviews.items.map((r) => (
              <div key={r.review_id} className="row-item" style={{ alignItems: "flex-start" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <strong>{r.username}</strong>
                    <StarRating value={r.stars} />
                    <span style={{ fontSize: 12, color: "var(--faint)" }}>
                      {new Date(r.created_at).toLocaleDateString("ja-JP")}
                    </span>
                  </div>
                  {r.text && <p style={{ margin: "6px 0 0" }}>{r.text}</p>}
                </div>
                {isLoggedIn && (
                  <button className="btn btn-ghost btn-sm" onClick={() => handleHelpful(r.review_id, true)}>
                    役に立った（{r.helpful_count}）
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
