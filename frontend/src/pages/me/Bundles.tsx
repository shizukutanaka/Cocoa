import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import * as bundleService from "../../services/bundleService";
import * as marketplaceService from "../../services/marketplaceService";
import { apiErrorMessage } from "../../services/apiClient";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";
import type { Bundle } from "../../types/api";

function statusBadge(bundle: Bundle) {
  return bundle.is_active ? (
    <span className="badge badge-success">公開中</span>
  ) : (
    <span className="badge">一時停止中</span>
  );
}

export function Bundles() {
  usePageTitle("バンドル管理");
  const { show } = useToast();
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [discount, setDiscount] = useState(15);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const { data: bundles, isLoading } = useQuery({
    queryKey: ["my-bundles"],
    queryFn: () => bundleService.listMyBundles(true, 50, 0),
  });

  // Only active listings can be validly bundled server-side.
  const { data: myListings } = useQuery({
    queryKey: ["my-listings-active"],
    queryFn: () => marketplaceService.myListings(false, 100, 0),
  });

  function toggleSelected(listingId: string) {
    setSelectedIds((prev) =>
      prev.includes(listingId) ? prev.filter((id) => id !== listingId) : [...prev, listingId]
    );
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (selectedIds.length < 2) {
      setError("バンドルには2件以上のリスティングを選択してください");
      return;
    }
    setBusy(true);
    try {
      await bundleService.createBundle({
        name,
        description,
        listing_ids: selectedIds,
        discount_percent: discount,
      });
      setName("");
      setDescription("");
      setSelectedIds([]);
      queryClient.invalidateQueries({ queryKey: ["my-bundles"] });
      show("バンドルを作成しました");
    } catch (err) {
      setError(apiErrorMessage(err, "バンドルの作成に失敗しました"));
    } finally {
      setBusy(false);
    }
  }

  async function handleToggleActive(bundle: Bundle) {
    try {
      if (bundle.is_active) {
        await bundleService.deactivateBundle(bundle.bundle_id);
      } else {
        await bundleService.activateBundle(bundle.bundle_id);
      }
      queryClient.invalidateQueries({ queryKey: ["my-bundles"] });
    } catch (err) {
      show(apiErrorMessage(err, "更新に失敗しました"), "error");
    }
  }

  async function handleDelete(bundleId: string) {
    if (!window.confirm("このバンドルを削除しますか？（元に戻せません）")) return;
    try {
      await bundleService.deleteBundle(bundleId);
      queryClient.invalidateQueries({ queryKey: ["my-bundles"] });
    } catch (err) {
      show(apiErrorMessage(err, "削除に失敗しました"), "error");
    }
  }

  return (
    <div>
      <h1>バンドル管理</h1>
      <p style={{ color: "var(--muted)", fontSize: 14 }}>
        自分のリスティングを2件以上まとめて、割引価格のセット商品として販売できます。
      </p>

      <div className="card card-pad" style={{ maxWidth: 560, marginBottom: 24 }}>
        {error && <div className="form-error-banner">{error}</div>}
        <form onSubmit={handleCreate}>
          <div className="field">
            <label htmlFor="bundle-name">バンドル名</label>
            <input id="bundle-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
          </div>
          <div className="field">
            <label htmlFor="bundle-description">説明（任意）</label>
            <textarea
              id="bundle-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              maxLength={1000}
            />
          </div>
          <div className="field">
            <label htmlFor="bundle-discount">割引率（%）</label>
            <input
              id="bundle-discount"
              type="number"
              min={0}
              max={90}
              value={discount}
              onChange={(e) => setDiscount(Number(e.target.value))}
              required
            />
          </div>
          <div className="field">
            <label>含めるリスティング（2件以上）</label>
            {!myListings || myListings.items.length === 0 ? (
              <div style={{ fontSize: 13, color: "var(--muted)" }}>
                公開中のリスティングがありません。先に出品してください。
              </div>
            ) : (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  maxHeight: 200,
                  overflowY: "auto",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-sm)",
                  padding: 10,
                }}
              >
                {myListings.items.map((listing) => (
                  <label key={listing.listing_id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(listing.listing_id)}
                      onChange={() => toggleSelected(listing.listing_id)}
                    />
                    {listing.name}
                    <span style={{ color: "var(--faint)", fontSize: 12 }}>
                      ({listing.is_free ? "無料" : `${listing.price_credits.toLocaleString()} cr`})
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? "作成中..." : "バンドルを作成"}
          </button>
        </form>
      </div>

      {isLoading ? (
        <CenterSpinner />
      ) : !bundles || bundles.items.length === 0 ? (
        <div className="empty-state">まだバンドルがありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {bundles.items.map((bundle) => (
              <div key={bundle.bundle_id} className="row-item">
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <strong>{bundle.name}</strong>
                    <span className="listing-price">{bundle.discount_percent}% OFF</span>
                    {statusBadge(bundle)}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>{bundle.listing_count} 点セット</div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn btn-secondary btn-sm" onClick={() => handleToggleActive(bundle)}>
                    {bundle.is_active ? "一時停止" : "再開"}
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => handleDelete(bundle.bundle_id)}>
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
