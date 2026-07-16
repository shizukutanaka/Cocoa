import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import * as wishlistService from "../../services/wishlistService";
import { addToCart } from "../../services/cartService";
import { apiErrorMessage } from "../../services/apiClient";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";

export function Wishlist() {
  usePageTitle("ウィッシュリスト");
  const { show } = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["wishlist"],
    queryFn: () => wishlistService.getWishlist(true),
  });

  async function handleRemove(listingId: string) {
    await wishlistService.removeFromWishlist(listingId);
    queryClient.invalidateQueries({ queryKey: ["wishlist"] });
  }

  async function handleAddToCart(listingId: string) {
    try {
      await addToCart(listingId);
      queryClient.invalidateQueries({ queryKey: ["cart"] });
      show("カートに追加しました");
    } catch (err) {
      show(apiErrorMessage(err, "カートへの追加に失敗しました"), "error");
    }
  }

  if (isLoading) return <CenterSpinner />;

  return (
    <div>
      <h1>ウィッシュリスト</h1>
      {!data || data.items.length === 0 ? (
        <div className="empty-state">ウィッシュリストは空です。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {data.items.map((item) => (
              <div key={item.listing_id} className="row-item">
                <div>
                  {item.delisted ? (
                    <span style={{ color: "var(--faint)" }}>（削除されたリスティング）</span>
                  ) : (
                    <Link to={`/listings/${item.listing_id}`} style={{ fontWeight: 600 }}>
                      {item.snapshot_name}
                    </Link>
                  )}
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>
                    {item.price_dropped && <span className="badge badge-success">値下がりしました</span>}
                    {item.is_sold_out && <span className="badge badge-warning">在庫切れ</span>}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  {item.current_price != null && (
                    <span
                      className="listing-price"
                      style={item.price_dropped ? { color: "var(--success)" } : undefined}
                    >
                      {item.current_price.toLocaleString()} cr
                    </span>
                  )}
                  {item.is_available && (
                    <button className="btn btn-secondary btn-sm" onClick={() => handleAddToCart(item.listing_id)}>
                      カートに追加
                    </button>
                  )}
                  <button className="btn btn-ghost btn-sm" onClick={() => handleRemove(item.listing_id)}>
                    削除
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
