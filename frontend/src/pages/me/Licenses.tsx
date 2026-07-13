import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import * as licenseService from "../../services/licenseService";
import { getListing } from "../../services/marketplaceService";
import { apiErrorMessage } from "../../services/apiClient";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";
import type { LicenseKey } from "../../types/api";

// Same queryKey convention ListingDetail.tsx uses ("listing", id), so
// navigating from here to the listing page hits a warm cache instead of
// re-fetching.
function ListingLink({ listingId }: { listingId: string }) {
  const { data } = useQuery({
    queryKey: ["listing", listingId],
    queryFn: () => getListing(listingId),
  });
  return <Link to={`/listings/${listingId}`}>{data?.name ?? listingId}</Link>;
}

function LicenseRow({ license }: { license: LicenseKey }) {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [showActivateForm, setShowActivateForm] = useState(false);
  const [busy, setBusy] = useState(false);

  const atLimit = license.max_activations !== null && license.activation_count >= license.max_activations;

  async function handleActivate() {
    setBusy(true);
    try {
      await licenseService.activateLicense(license.key_id, note);
      setNote("");
      setShowActivateForm(false);
      queryClient.invalidateQueries({ queryKey: ["my-licenses"] });
      show("ライセンスをアクティベートしました");
    } catch (err) {
      show(apiErrorMessage(err, "アクティベートに失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="row-item" style={{ alignItems: "flex-start", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", width: "100%", alignItems: "center" }}>
        <div>
          <ListingLink listingId={license.listing_id} />
          <div style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--muted)", marginTop: 2 }}>
            {license.key}
          </div>
        </div>
        <div>
          {license.is_revoked ? (
            <span className="badge badge-warning">失効済み</span>
          ) : (
            <span className="badge badge-success">有効</span>
          )}
        </div>
      </div>

      <div style={{ fontSize: 13, color: "var(--muted)" }}>
        アクティベーション {license.activation_count}
        {license.max_activations !== null && ` / ${license.max_activations}`} 回 · 発行日{" "}
        {new Date(license.issued_at).toLocaleDateString("ja-JP")}
      </div>

      {license.is_revoked && (
        <div style={{ fontSize: 12, color: "var(--warning)" }}>
          失効理由: {license.revoked_reason || "(理由なし)"}
        </div>
      )}

      {license.activations.length > 0 && (
        <div style={{ fontSize: 12, color: "var(--faint)" }}>
          {license.activations.map((a) => (
            <div key={a.activation_id}>
              {new Date(a.activated_at).toLocaleString("ja-JP")}
              {a.note && ` — ${a.note}`}
            </div>
          ))}
        </div>
      )}

      {!license.is_revoked &&
        (showActivateForm ? (
          <div style={{ display: "flex", gap: 8, width: "100%" }}>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="用途メモ（例: VRChatワールド名）"
              maxLength={200}
              style={{ flex: 1, fontSize: 13, padding: "4px 8px" }}
              aria-label="アクティベーションのメモ"
            />
            <button className="btn btn-secondary btn-sm" onClick={handleActivate} disabled={busy}>
              {busy ? "処理中..." : "アクティベート"}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowActivateForm(false)}>
              キャンセル
            </button>
          </div>
        ) : (
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setShowActivateForm(true)}
            disabled={atLimit}
            title={atLimit ? "アクティベーション上限に達しています" : undefined}
          >
            {atLimit ? "上限到達" : "アクティベートする"}
          </button>
        ))}
    </div>
  );
}

export function Licenses() {
  usePageTitle("マイライセンス");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["my-licenses"],
    queryFn: () => licenseService.getMyLicenses(50, 0),
  });

  if (isLoading) return <CenterSpinner />;

  return (
    <div>
      <h1>マイライセンス</h1>
      <p style={{ color: "var(--muted)", fontSize: 14 }}>
        購入したアバターには自動的にライセンスキーが発行されます。使用する環境ごとにアクティベートして記録できます。
      </p>
      {isError ? (
        <div className="empty-state">読み込みに失敗しました。</div>
      ) : !data || data.items.length === 0 ? (
        <div className="empty-state">まだライセンスキーがありません。有料リスティングを購入すると発行されます。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {data.items.map((license) => (
              <LicenseRow key={license.key_id} license={license} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
