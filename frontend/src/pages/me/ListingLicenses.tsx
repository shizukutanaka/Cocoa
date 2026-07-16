import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import * as licenseService from "../../services/licenseService";
import { getListing } from "../../services/marketplaceService";
import { apiErrorMessage } from "../../services/apiClient";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";

export function ListingLicenses() {
  const { listingId } = useParams<{ listingId: string }>();
  const { show } = useToast();
  const queryClient = useQueryClient();

  const { data: listing } = useQuery({
    queryKey: ["listing", listingId],
    queryFn: () => getListing(listingId!),
    enabled: !!listingId,
  });

  usePageTitle(listing ? `ライセンス — ${listing.name}` : "ライセンス管理");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["listing-licenses", listingId],
    queryFn: () => licenseService.getListingLicenses(listingId!),
    enabled: !!listingId,
  });

  async function handleRevoke(keyId: string) {
    const reason = window.prompt("失効理由（任意）");
    if (reason === null) return; // cancelled
    try {
      await licenseService.revokeLicense(keyId, reason);
      queryClient.invalidateQueries({ queryKey: ["listing-licenses", listingId] });
      show("ライセンスを失効させました");
    } catch (err) {
      show(apiErrorMessage(err, "失効に失敗しました"), "error");
    }
  }

  if (isLoading) return <CenterSpinner />;

  return (
    <div>
      <h1>ライセンス管理{listing && ` — ${listing.name}`}</h1>
      <p style={{ color: "var(--muted)", fontSize: 14 }}>
        このリスティングの購入者に発行されたライセンスキー一覧です。不正利用が疑われる場合は失効させられます。
      </p>
      {isError ? (
        <div className="empty-state">読み込みに失敗しました（自分が出品したリスティングのみ閲覧できます）。</div>
      ) : !data || data.items.length === 0 ? (
        <div className="empty-state">まだ発行されたライセンスはありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {data.items.map((license) => (
              <div key={license.key_id} className="row-item">
                <div>
                  <code style={{ fontSize: 13 }}>{license.key}</code>
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>
                    保有者: {license.holder_id} · アクティベーション {license.activation_count}
                    {license.max_activations !== null && ` / ${license.max_activations}`} 回 · 発行日{" "}
                    {new Date(license.issued_at).toLocaleDateString("ja-JP")}
                  </div>
                </div>
                <div>
                  {license.is_revoked ? (
                    <span className="badge badge-warning">失効済み</span>
                  ) : (
                    <button className="btn btn-ghost btn-sm" onClick={() => handleRevoke(license.key_id)}>
                      失効させる
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
