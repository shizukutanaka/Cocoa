import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import * as savedSearchService from "../../services/savedSearchService";
import { apiErrorMessage } from "../../services/apiClient";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";
import type { SavedSearch } from "../../types/api";

// Rebuild the marketplace URL a saved search points at, so "実行" lands the
// user on exactly the filtered listing they saved.
function toMarketplaceUrl(ss: SavedSearch): string {
  const p = new URLSearchParams();
  if (ss.query) p.set("q", ss.query);
  if (ss.filters.category) p.set("category", ss.filters.category);
  if (ss.filters.tags && ss.filters.tags.length) p.set("tags", ss.filters.tags.join(","));
  if (ss.filters.sort_by) p.set("sort_by", ss.filters.sort_by);
  const qs = p.toString();
  return qs ? `/?${qs}` : "/";
}

export function SavedSearches() {
  usePageTitle("保存した検索");
  const { show } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["saved-searches"],
    queryFn: savedSearchService.listSavedSearches,
  });

  async function handleDelete(searchId: string) {
    if (!window.confirm("この保存検索を削除しますか？")) return;
    try {
      await savedSearchService.deleteSavedSearch(searchId);
      queryClient.invalidateQueries({ queryKey: ["saved-searches"] });
    } catch (err) {
      show(apiErrorMessage(err, "削除に失敗しました"), "error");
    }
  }

  async function handleToggleNotify(ss: SavedSearch) {
    try {
      await savedSearchService.setSavedSearchNotify(ss.search_id, !ss.notify_on_match);
      queryClient.invalidateQueries({ queryKey: ["saved-searches"] });
    } catch (err) {
      show(apiErrorMessage(err, "通知設定の更新に失敗しました"), "error");
    }
  }

  if (isLoading) return <CenterSpinner />;

  return (
    <div>
      <h1>保存した検索</h1>
      <p style={{ color: "var(--muted)", fontSize: 14 }}>
        通知をオンにすると、条件に一致する新着アバターが出品されたときに通知が届きます。
      </p>
      {!data || data.items.length === 0 ? (
        <div className="empty-state">
          保存した検索はありません。マーケットプレイスで条件を指定し「この検索を保存」から追加できます。
        </div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {data.items.map((ss) => (
              <div key={ss.search_id} className="row-item" style={{ alignItems: "flex-start" }}>
                <div>
                  <div style={{ fontWeight: 600 }}>{ss.name}</div>
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>
                    {ss.query ? `「${ss.query}」` : "（キーワードなし）"}
                    {ss.filters.category && ` · ${ss.filters.category}`}
                    {ss.filters.tags && ss.filters.tags.length > 0 && ` · ${ss.filters.tags.join(", ")}`}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 4 }}>
                    <input
                      type="checkbox"
                      checked={ss.notify_on_match}
                      onChange={() => handleToggleNotify(ss)}
                    />
                    通知
                  </label>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => navigate(toMarketplaceUrl(ss))}
                  >
                    実行
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => handleDelete(ss.search_id)}
                    aria-label={`「${ss.name}」を削除`}
                  >
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
