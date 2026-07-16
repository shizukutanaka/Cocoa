import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import * as marketplaceService from "../../services/marketplaceService";
import * as userService from "../../services/userService";
import { apiErrorMessage } from "../../services/apiClient";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { CenterSpinner } from "../../components/Spinner";
import type { Listing, PublicProfile } from "../../types/api";

function StockLimitControl({ listing }: { listing: Listing }) {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [value, setValue] = useState(listing.stock_limit != null ? String(listing.stock_limit) : "");
  const [busy, setBusy] = useState(false);

  async function apply(next: number | null) {
    setBusy(true);
    try {
      await marketplaceService.setStockLimit(listing.listing_id, next);
      queryClient.invalidateQueries({ queryKey: ["my-listings"] });
      show(next === null ? "在庫を無制限にしました" : `在庫上限を${next}に設定しました`);
    } catch (err) {
      show(apiErrorMessage(err, "在庫設定の更新に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 4 }}>
        在庫: {listing.stock_limit == null ? "無制限" : `残り ${listing.stock_remaining} / ${listing.stock_limit}`}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          type="number"
          min={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="上限数"
          aria-label={`「${listing.name}」の在庫上限`}
          style={{ width: 100, fontSize: 13, padding: "4px 8px" }}
        />
        <button
          className="btn btn-secondary btn-sm"
          disabled={busy || !value}
          onClick={() => apply(Number(value))}
        >
          設定
        </button>
        {listing.stock_limit != null && (
          <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => apply(null)}>
            無制限にする
          </button>
        )}
      </div>
    </div>
  );
}

function TransferControl({ listing }: { listing: Listing }) {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<PublicProfile | null>(null);
  const [busy, setBusy] = useState(false);
  const debouncedQuery = useDebouncedValue(query, 300);

  const { data: results } = useQuery({
    queryKey: ["user-search", debouncedQuery],
    queryFn: () => userService.searchUsers(debouncedQuery, 8),
    enabled: debouncedQuery.trim().length >= 2 && !selected,
  });

  async function handleTransfer() {
    if (!selected) return;
    if (
      !window.confirm(
        `「${listing.name}」を @${selected.username} に譲渡しますか？この操作は取り消せません。`
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      await marketplaceService.transferListing(listing.listing_id, selected.user_id, selected.username);
      queryClient.invalidateQueries({ queryKey: ["my-listings"] });
      show("譲渡しました");
    } catch (err) {
      show(apiErrorMessage(err, "譲渡に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 4 }}>
        リスティングを別のユーザーに譲渡します。
      </div>
      {selected ? (
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="badge">@{selected.username}</span>
          <button className="btn btn-primary btn-sm" onClick={handleTransfer} disabled={busy}>
            {busy ? "処理中..." : "譲渡を確定"}
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => setSelected(null)}>
            変更
          </button>
        </div>
      ) : (
        <div style={{ position: "relative", maxWidth: 240 }}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="譲渡先のユーザー名で検索"
            aria-label={`「${listing.name}」の譲渡先を検索`}
            style={{ fontSize: 13, padding: "4px 8px", width: "100%" }}
          />
          {results && results.items.length > 0 && (
            <ul className="suggest-list" role="listbox">
              {results.items.map((u) => (
                <li key={u.user_id}>
                  <button type="button" className="suggest-item" onClick={() => setSelected(u)}>
                    @{u.username}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function ListingRow({ listing }: { listing: Listing }) {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);

  async function handleUnpublish() {
    if (!confirm("このリスティングを取り下げますか？")) return;
    try {
      await marketplaceService.unpublishListing(listing.listing_id);
      show("取り下げました");
      queryClient.invalidateQueries({ queryKey: ["my-listings"] });
    } catch (err) {
      show(apiErrorMessage(err, "取り下げに失敗しました"), "error");
    }
  }

  return (
    <div className="row-item" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
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
          <button className="btn btn-ghost btn-sm" onClick={() => setExpanded((v) => !v)}>
            {expanded ? "閉じる" : "詳細設定"}
          </button>
          {listing.is_active && (
            <button className="btn btn-ghost btn-sm" onClick={handleUnpublish}>
              取り下げ
            </button>
          )}
        </div>
      </div>

      {expanded && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, paddingTop: 8, borderTop: "1px solid var(--border)" }}>
          <StockLimitControl listing={listing} />
          <TransferControl listing={listing} />
        </div>
      )}
    </div>
  );
}

export function MyListings() {
  usePageTitle("出品管理");

  const { data, isLoading } = useQuery({
    queryKey: ["my-listings"],
    queryFn: () => marketplaceService.myListings(true, 50, 0),
  });

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
              <ListingRow key={listing.listing_id} listing={listing} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
