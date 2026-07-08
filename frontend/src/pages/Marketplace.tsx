import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { browseMarketplace } from "../services/marketplaceService";
import { CenterSpinner } from "../components/Spinner";

const PAGE_SIZE = 24;

export function Marketplace() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const sortBy = (params.get("sort_by") as "newest" | "downloads" | "rating" | "price_asc" | "price_desc") ?? "newest";
  const offset = Number(params.get("offset") ?? "0");
  const [qInput, setQInput] = useState(q);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["marketplace", q, sortBy, offset],
    queryFn: () => browseMarketplace({ q, sort_by: sortBy, limit: PAGE_SIZE, offset }),
  });

  function updateParams(patch: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    setParams(next);
  }

  function handleSearchSubmit(e: FormEvent) {
    e.preventDefault();
    updateParams({ q: qInput, offset: "0" });
  }

  return (
    <div>
      <h1>マーケットプレイス</h1>
      <form className="filters-bar" onSubmit={handleSearchSubmit}>
        <input
          type="text"
          placeholder="アバターを検索..."
          value={qInput}
          onChange={(e) => setQInput(e.target.value)}
        />
        <select value={sortBy} onChange={(e) => updateParams({ sort_by: e.target.value, offset: "0" })}>
          <option value="newest">新着順</option>
          <option value="downloads">ダウンロード数順</option>
          <option value="rating">評価順</option>
          <option value="price_asc">価格が安い順</option>
          <option value="price_desc">価格が高い順</option>
        </select>
        <button type="submit" className="btn btn-secondary">
          検索
        </button>
      </form>

      {isLoading && <CenterSpinner />}
      {isError && <div className="empty-state">読み込みに失敗しました。</div>}
      {data && data.items.length === 0 && <div className="empty-state">該当するアバターが見つかりませんでした。</div>}

      {data && data.items.length > 0 && (
        <>
          <div className="listing-grid">
            {data.items.map((listing) => (
              <Link key={listing.listing_id} to={`/listings/${listing.listing_id}`} className="card listing-card">
                <div className="listing-thumb">
                  {listing.thumbnail_url ? <img src={listing.thumbnail_url} alt="" /> : "No Image"}
                </div>
                <div className="listing-body">
                  <div className="listing-name">{listing.name}</div>
                  <div className="listing-meta">
                    <span>{listing.owner_username}</span>
                    <span className={listing.is_free ? "listing-price is-free" : "listing-price"}>
                      {listing.is_free ? "無料" : `${listing.price_credits.toLocaleString()} cr`}
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>

          <div className="pagination">
            <button
              className="btn btn-secondary"
              disabled={offset === 0}
              onClick={() => updateParams({ offset: String(Math.max(0, offset - PAGE_SIZE)) })}
            >
              前へ
            </button>
            <button
              className="btn btn-secondary"
              disabled={!data.has_more}
              onClick={() => updateParams({ offset: String(offset + PAGE_SIZE) })}
            >
              次へ
            </button>
          </div>
        </>
      )}
    </div>
  );
}
