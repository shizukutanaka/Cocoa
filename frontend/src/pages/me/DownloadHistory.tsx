import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import * as marketplaceService from "../../services/marketplaceService";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";
import { ParameterDelivery } from "../../components/ParameterDelivery";
import { useToast } from "../../hooks/useToast";
import { apiErrorMessage } from "../../services/apiClient";
import type { AvatarData } from "../../types/api";

export function DownloadHistory() {
  usePageTitle("ダウンロード履歴");
  const { show } = useToast();
  // Which listing's parameters are currently shown, and the data itself.
  const [openId, setOpenId] = useState<string | null>(null);
  const [delivered, setDelivered] = useState<AvatarData | null>(null);
  const [retrievingId, setRetrievingId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["download-history"],
    queryFn: () => marketplaceService.getDownloadHistory(50, 0),
  });

  // Everything in this list is already owned, so retrieval is always free.
  async function handleRetrieve(listingId: string) {
    setRetrievingId(listingId);
    try {
      const avatar = await marketplaceService.downloadAvatar(listingId);
      setDelivered(avatar);
      setOpenId(listingId);
    } catch (err) {
      show(apiErrorMessage(err, "パラメータの取得に失敗しました"), "error");
    } finally {
      setRetrievingId(null);
    }
  }

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
              <div key={`${entry.listing_id}-${i}`}>
                <div className="row-item">
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
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{ fontSize: 13, color: "var(--faint)" }}>
                      {new Date(entry.downloaded_at).toLocaleString("ja-JP")}
                    </span>
                    {/* A delisted listing can no longer be fetched (download()
                        returns None for inactive listings), so don't offer it. */}
                    {entry.is_active !== false && entry.name && (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() =>
                          openId === entry.listing_id
                            ? (setOpenId(null), setDelivered(null))
                            : handleRetrieve(entry.listing_id)
                        }
                        disabled={retrievingId === entry.listing_id}
                        aria-label={`${entry.name} のパラメータを取得`}
                      >
                        {retrievingId === entry.listing_id
                          ? "取得中..."
                          : openId === entry.listing_id
                            ? "閉じる"
                            : "パラメータを取得"}
                      </button>
                    )}
                  </div>
                </div>
                {openId === entry.listing_id && delivered && (
                  <ParameterDelivery data={delivered} />
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
