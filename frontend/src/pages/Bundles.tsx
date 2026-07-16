import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import * as bundleService from "../services/bundleService";
import { getListing } from "../services/marketplaceService";
import { apiErrorMessage } from "../services/apiClient";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { usePageTitle } from "../hooks/usePageTitle";
import { CenterSpinner } from "../components/Spinner";
import type { Bundle } from "../types/api";

function BundleCard({ bundle }: { bundle: Bundle }) {
  const { user } = useAuth();
  const { show } = useToast();
  const queryClient = useQueryClient();

  // Bundle.to_dict() only carries listing_ids -- fetch each constituent
  // listing (through the shared ["listing", id] cache ListingDetail.tsx
  // uses) to compute and display the combined price.
  const { data: listings, isLoading } = useQuery({
    queryKey: ["bundle-listings", bundle.bundle_id],
    queryFn: () => Promise.all(bundle.listing_ids.map((id) => getListing(id))),
  });

  const originalTotal = listings?.reduce((sum, l) => sum + l.price_credits, 0) ?? 0;
  const discountedTotal = Math.max(0, Math.floor((originalTotal * (100 - bundle.discount_percent)) / 100));
  const isSelf = user?.user_id === bundle.creator_id;

  async function handlePurchase() {
    try {
      const result = await bundleService.purchaseBundle(bundle.bundle_id);
      show(`${result.total_charged.toLocaleString()} クレジットで購入しました`);
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    } catch (err) {
      show(apiErrorMessage(err, "購入に失敗しました"), "error");
    }
  }

  return (
    <div className="card card-pad">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 16 }}>{bundle.name}</div>
          <div style={{ fontSize: 13, color: "var(--muted)" }}>
            by {bundle.creator_username} · {bundle.listing_count} 点セット
          </div>
        </div>
        <span className="badge badge-success">{bundle.discount_percent}% OFF</span>
      </div>

      {bundle.description && <p style={{ fontSize: 14, marginTop: 8 }}>{bundle.description}</p>}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
        {listings?.map((l) => (
          <Link key={l.listing_id} to={`/listings/${l.listing_id}`} className="badge">
            {l.name}
          </Link>
        ))}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 14 }}>
        {isLoading ? (
          <span style={{ fontSize: 13, color: "var(--faint)" }}>価格計算中...</span>
        ) : (
          <span className="listing-price">
            {bundle.discount_percent > 0 && (
              <s style={{ color: "var(--faint)", fontWeight: 400, marginRight: 6 }}>
                {originalTotal.toLocaleString()} cr
              </s>
            )}
            {discountedTotal.toLocaleString()} cr
          </span>
        )}
        {user && !isSelf && (
          <button className="btn btn-primary btn-sm" onClick={handlePurchase}>
            まとめて購入
          </button>
        )}
      </div>
    </div>
  );
}

export function Bundles() {
  usePageTitle("バンドル");

  const { data, isLoading } = useQuery({
    queryKey: ["bundles"],
    queryFn: () => bundleService.listActiveBundles(50, 0),
  });

  if (isLoading) return <CenterSpinner />;

  return (
    <div>
      <h1>バンドル</h1>
      <p style={{ color: "var(--muted)", fontSize: 14 }}>
        クリエイターがまとめたセット商品を割引価格で購入できます。
      </p>
      {!data || data.items.length === 0 ? (
        <div className="empty-state">現在公開中のバンドルはありません。</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
          {data.items.map((bundle) => (
            <BundleCard key={bundle.bundle_id} bundle={bundle} />
          ))}
        </div>
      )}
    </div>
  );
}
