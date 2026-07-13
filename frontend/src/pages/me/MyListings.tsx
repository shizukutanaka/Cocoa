import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import * as marketplaceService from "../../services/marketplaceService";
import { apiErrorMessage } from "../../services/apiClient";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";

export function MyListings() {
  usePageTitle("出品管理");
  const { show } = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["my-listings"],
    queryFn: () => marketplaceService.myListings(true, 50, 0),
  });

  async function handleUnpublish(listingId: string) {
    if (!confirm("このリスティングを取り下げますか？")) return;
    try {
      await marketplaceService.unpublishListing(listingId);
      show("取り下げました");
      queryClient.invalidateQueries({ queryKey: ["my-listings"] });
    } catch (err) {
      show(apiErrorMessage(err, "取り下げに失敗しました"), "error");
    }
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h1>出品管理</h1>
        <Link to="/me/listings/new" className="btn btn-primary btn-sm">
          新規出品
        </Link>
      </div>

      {isLoading ? (
        <CenterSpinner />
      ) : !data || data.items.length === 0 ? (
        <div className="empty-state">まだ出品がありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {data.items.map((listing) => (
              <div key={listing.listing_id} className="row-item">
                <div>
                  <Link to={`/listings/${listing.listing_id}`} style={{ fontWeight: 600 }}>
                    {listing.name}
                  </Link>
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>
                    {listing.download_count.toLocaleString()} ダウンロード ·{" "}
                    {listing.rating_count > 0 ? `評価 ${listing.average_rating.toFixed(1)}` : "評価なし"}
                    {!listing.is_active && " · 非公開"}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span className="listing-price">{listing.is_free ? "無料" : `${listing.price_credits.toLocaleString()} cr`}</span>
                  <Link
                    to={`/me/listings/${listing.listing_id}/licenses`}
                    className="btn btn-ghost btn-sm"
                    aria-label={`「${listing.name}」のライセンス管理`}
                  >
                    ライセンス
                  </Link>
                  {listing.is_active && (
                    <button className="btn btn-ghost btn-sm" onClick={() => handleUnpublish(listing.listing_id)}>
                      取り下げ
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
