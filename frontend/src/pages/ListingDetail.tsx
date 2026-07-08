import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { getListing } from "../services/marketplaceService";
import { addToCart } from "../services/cartService";
import { CenterSpinner } from "../components/Spinner";
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

        {!isOwnListing && !listing.is_sold_out && (
          <button className="btn btn-primary" onClick={handleAddToCart} disabled={addingToCart}>
            {addingToCart ? "追加中..." : "カートに追加"}
          </button>
        )}
        {isOwnListing && <p style={{ color: "var(--muted)" }}>これはあなたが出品したリスティングです。</p>}
      </div>
    </div>
  );
}
