import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  browseMarketplace,
  getCategories,
  getSuggestions,
  getTrending,
} from "../services/marketplaceService";
import { createSavedSearch } from "../services/savedSearchService";
import { CenterSpinner } from "../components/Spinner";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { usePageTitle } from "../hooks/usePageTitle";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { apiErrorMessage } from "../services/apiClient";

const PAGE_SIZE = 24;

type SortKey = "newest" | "downloads" | "rating" | "price_asc" | "price_desc";

export function Marketplace() {
  usePageTitle("マーケットプレイス");
  const { user } = useAuth();
  const { show } = useToast();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const category = params.get("category") ?? "";
  const tags = params.get("tags") ?? "";
  const sortBy = (params.get("sort_by") as SortKey) ?? "newest";
  const offset = Number(params.get("offset") ?? "0");

  const [qInput, setQInput] = useState(q);
  const [showSuggest, setShowSuggest] = useState(false);
  const debouncedInput = useDebouncedValue(qInput, 250);
  const searchBoxRef = useRef<HTMLDivElement>(null);

  // Keep the input in sync when the URL changes from outside (e.g. a saved
  // search navigation or the browser back button).
  useEffect(() => {
    setQInput(q);
  }, [q]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["marketplace", q, category, tags, sortBy, offset],
    queryFn: () =>
      browseMarketplace({ q, category, tags, sort_by: sortBy, limit: PAGE_SIZE, offset }),
  });

  const { data: categories } = useQuery({
    queryKey: ["marketplace-categories"],
    queryFn: getCategories,
  });

  const { data: suggestions } = useQuery({
    queryKey: ["suggest", debouncedInput],
    queryFn: () => getSuggestions(debouncedInput),
    enabled: debouncedInput.trim().length >= 2 && showSuggest,
  });

  // Dismiss the suggestion dropdown when clicking outside the search box.
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (searchBoxRef.current && !searchBoxRef.current.contains(e.target as Node)) {
        setShowSuggest(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

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
    setShowSuggest(false);
    updateParams({ q: qInput, offset: "0" });
  }

  function applySuggestion(s: string) {
    setQInput(s);
    setShowSuggest(false);
    updateParams({ q: s, offset: "0" });
  }

  async function handleSaveSearch() {
    const name = window.prompt("この検索の名前を入力してください", q || category || "検索");
    if (!name) return;
    try {
      await createSavedSearch(name, q, {
        category: category || undefined,
        tags: tags ? tags.split(",").map((t) => t.trim()).filter(Boolean) : undefined,
        sort_by: sortBy,
      });
      show("検索を保存しました");
    } catch (err) {
      show(apiErrorMessage(err, "検索の保存に失敗しました"), "error");
    }
  }

  const hasFilters = Boolean(q || category || tags);

  // Discovery strip for the default landing view only -- once the user is
  // actively filtering/searching, the main grid IS the answer and the strip
  // would just push results below the fold.
  const { data: trending } = useQuery({
    queryKey: ["trending"],
    queryFn: () => getTrending(6),
    enabled: !hasFilters && offset === 0,
  });

  return (
    <div>
      <h1>マーケットプレイス</h1>
      <form className="filters-bar" onSubmit={handleSearchSubmit} role="search">
        <div className="search-box" ref={searchBoxRef}>
          <input
            type="text"
            placeholder="アバターを検索..."
            aria-label="アバターを検索"
            value={qInput}
            autoComplete="off"
            onChange={(e) => {
              setQInput(e.target.value);
              setShowSuggest(true);
            }}
            onFocus={() => setShowSuggest(true)}
          />
          {showSuggest && suggestions && suggestions.length > 0 && (
            <ul className="suggest-list" role="listbox">
              {suggestions.map((s) => (
                <li key={s}>
                  <button type="button" className="suggest-item" onClick={() => applySuggestion(s)}>
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <select
          value={category}
          aria-label="カテゴリで絞り込み"
          onChange={(e) => updateParams({ category: e.target.value, offset: "0" })}
        >
          <option value="">全カテゴリ</option>
          {categories?.items.map((c) => (
            <option key={c.category} value={c.category}>
              {c.category}（{c.count}）
            </option>
          ))}
        </select>

        <input
          type="text"
          placeholder="タグ（カンマ区切り）"
          aria-label="タグで絞り込み"
          defaultValue={tags}
          onBlur={(e) => updateParams({ tags: e.target.value.trim(), offset: "0" })}
        />

        <select
          value={sortBy}
          aria-label="並び順"
          onChange={(e) => updateParams({ sort_by: e.target.value, offset: "0" })}
        >
          <option value="newest">新着順</option>
          <option value="downloads">ダウンロード数順</option>
          <option value="rating">評価順</option>
          <option value="price_asc">価格が安い順</option>
          <option value="price_desc">価格が高い順</option>
        </select>

        <button type="submit" className="btn btn-secondary">
          検索
        </button>
        {user && hasFilters && (
          <button type="button" className="btn btn-ghost" onClick={handleSaveSearch}>
            この検索を保存
          </button>
        )}
      </form>

      {!hasFilters && offset === 0 && trending && trending.length > 0 && (
        <section style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: 17 }}>🔥 トレンド</h2>
          <div className="related-grid">
            {trending.map((listing) => (
              <Link key={listing.listing_id} to={`/listings/${listing.listing_id}`} className="card listing-card">
                <div className="listing-thumb">
                  {listing.thumbnail_url ? <img src={listing.thumbnail_url} alt="" loading="lazy" /> : "No Image"}
                </div>
                <div className="listing-body">
                  <div className="listing-name">{listing.name}</div>
                  <div className="listing-meta">
                    <span>{listing.download_count.toLocaleString()} DL</span>
                    <span className={listing.is_free ? "listing-price is-free" : "listing-price"}>
                      {listing.is_free ? "無料" : `${listing.price_credits.toLocaleString()} cr`}
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {isLoading && <CenterSpinner />}
      {isError && <div className="empty-state">読み込みに失敗しました。</div>}
      {data && data.items.length === 0 && (
        <div className="empty-state">該当するアバターが見つかりませんでした。</div>
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="listing-grid">
            {data.items.map((listing) => (
              <Link key={listing.listing_id} to={`/listings/${listing.listing_id}`} className="card listing-card">
                <div className="listing-thumb">
                  {listing.thumbnail_url ? (
                    <img src={listing.thumbnail_url} alt="" loading="lazy" />
                  ) : (
                    "No Image"
                  )}
                </div>
                <div className="listing-body">
                  <div className="listing-name">
                    {listing.name}
                    {listing.is_ai_generated && (
                      <span className="badge badge-ai" title="AI生成コンテンツを含む">
                        AI
                      </span>
                    )}
                  </div>
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
