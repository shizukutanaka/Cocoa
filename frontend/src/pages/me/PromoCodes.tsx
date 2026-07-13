import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import * as marketplaceService from "../../services/marketplaceService";
import { apiErrorMessage } from "../../services/apiClient";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";
import type { PromoCode } from "../../types/api";

function statusBadge(pc: PromoCode) {
  if (!pc.is_active) return <span className="badge">無効化済み</span>;
  if (!pc.is_valid) {
    const exhausted = pc.max_uses !== null && pc.uses_count >= pc.max_uses;
    return <span className="badge badge-warning">{exhausted ? "使用上限到達" : "期限切れ"}</span>;
  }
  return <span className="badge badge-success">有効</span>;
}

export function PromoCodes() {
  usePageTitle("プロモコード");
  const { show } = useToast();
  const queryClient = useQueryClient();

  const [code, setCode] = useState("");
  const [discount, setDiscount] = useState(10);
  const [listingId, setListingId] = useState("");
  const [maxUses, setMaxUses] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const { data: codes, isLoading } = useQuery({
    queryKey: ["my-promo-codes"],
    queryFn: marketplaceService.listMyPromoCodes,
  });

  // For the listing-restriction dropdown: creator's own active listings.
  const { data: myListings } = useQuery({
    queryKey: ["my-listings"],
    queryFn: () => marketplaceService.myListings(false, 50, 0),
  });

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await marketplaceService.createPromoCode({
        code,
        discount_percent: discount,
        listing_id: listingId || null,
        max_uses: maxUses ? Number(maxUses) : null,
        // datetime-local gives "YYYY-MM-DDTHH:mm" (no zone); the backend
        // normalizes zoneless ISO strings to UTC.
        expires_at: expiresAt || null,
      });
      setCode("");
      queryClient.invalidateQueries({ queryKey: ["my-promo-codes"] });
      show("プロモコードを作成しました");
    } catch (err) {
      setError(apiErrorMessage(err, "プロモコードの作成に失敗しました"));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeactivate(codeId: string) {
    if (!window.confirm("このプロモコードを無効化しますか？（元に戻せません）")) return;
    try {
      await marketplaceService.deactivatePromoCode(codeId);
      queryClient.invalidateQueries({ queryKey: ["my-promo-codes"] });
    } catch (err) {
      show(apiErrorMessage(err, "無効化に失敗しました"), "error");
    }
  }

  const listingNameById = new Map(myListings?.items.map((l) => [l.listing_id, l.name]) ?? []);

  return (
    <div>
      <h1>プロモコード</h1>
      <p style={{ color: "var(--muted)", fontSize: 14 }}>
        購入者がカートで入力すると割引が適用される、あなたのリスティング用の割引コードです。
      </p>

      <div className="card card-pad" style={{ maxWidth: 560, marginBottom: 24 }}>
        {error && <div className="form-error-banner">{error}</div>}
        <form onSubmit={handleCreate}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="field">
              <label htmlFor="promo-code">コード</label>
              <input
                id="promo-code"
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="SUMMER10"
                maxLength={30}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="promo-discount">割引率（%）</label>
              <input
                id="promo-discount"
                type="number"
                min={1}
                max={99}
                value={discount}
                onChange={(e) => setDiscount(Number(e.target.value))}
                required
              />
            </div>
          </div>
          <div className="field">
            <label htmlFor="promo-listing">対象リスティング</label>
            <select id="promo-listing" value={listingId} onChange={(e) => setListingId(e.target.value)}>
              <option value="">すべての自分のリスティング</option>
              {myListings?.items.map((l) => (
                <option key={l.listing_id} value={l.listing_id}>
                  {l.name}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="field">
              <label htmlFor="promo-max-uses">使用回数上限（任意）</label>
              <input
                id="promo-max-uses"
                type="number"
                min={1}
                value={maxUses}
                onChange={(e) => setMaxUses(e.target.value)}
                placeholder="無制限"
              />
            </div>
            <div className="field">
              <label htmlFor="promo-expires">有効期限（任意）</label>
              <input
                id="promo-expires"
                type="datetime-local"
                value={expiresAt}
                onChange={(e) => setExpiresAt(e.target.value)}
              />
            </div>
          </div>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? "作成中..." : "作成する"}
          </button>
        </form>
      </div>

      {isLoading ? (
        <CenterSpinner />
      ) : !codes || codes.items.length === 0 ? (
        <div className="empty-state">まだプロモコードがありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {codes.items.map((pc) => (
              <div key={pc.code_id} className="row-item">
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <code style={{ fontWeight: 700 }}>{pc.code}</code>
                    <span className="listing-price">{pc.discount_percent}% OFF</span>
                    {statusBadge(pc)}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>
                    {pc.listing_id
                      ? `対象: ${listingNameById.get(pc.listing_id) ?? pc.listing_id}`
                      : "対象: すべての自分のリスティング"}
                    {" · "}使用 {pc.uses_count}
                    {pc.max_uses !== null && ` / ${pc.max_uses}`} 回
                    {pc.expires_at && ` · 期限 ${new Date(pc.expires_at).toLocaleString("ja-JP")}`}
                  </div>
                </div>
                {pc.is_active && (
                  <button className="btn btn-ghost btn-sm" onClick={() => handleDeactivate(pc.code_id)}>
                    無効化
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
