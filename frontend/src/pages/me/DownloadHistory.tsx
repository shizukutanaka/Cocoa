import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import * as marketplaceService from "../../services/marketplaceService";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";

export function DownloadHistory() {
  usePageTitle("ダウンロード履歴");

  const { data, isLoading } = useQuery({
    queryKey: ["download-history"],
    queryFn: () => marketplaceService.getDownloadHistory(50, 0),
  });

  return (
    <div>
      <h1>ダウンロード履歴</h1>

      {isLoading ? (
        <CenterSpinner />
      ) : !data || data.items.length === 0 ? (
        <div className="empty-state">まだダウンロードした作品がありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {data.items.map((entry, i) => (
              <div key={`${entry.listing_id}-${i}`} className="row-item">
                <div>
                  {entry.name ? (
                    <Link to={`/listings/${entry.listing_id}`} style={{ fontWeight: 600 }}>
                      {entry.name}
                    </Link>
                  ) : (
                    <span style={{ color: "var(--faint)" }}>（削除されたリスティング）</span>
                  )}
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>
                    {entry.owner_username}
                    {entry.is_active === false && " · 非公開"}
                  </div>
                </div>
                <span style={{ fontSize: 13, color: "var(--faint)" }}>
                  {new Date(entry.downloaded_at).toLocaleString("ja-JP")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
