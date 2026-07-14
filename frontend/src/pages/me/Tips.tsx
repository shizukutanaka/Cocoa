import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import * as tipService from "../../services/tipService";
import { getPublicProfile } from "../../services/userService";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";

// Tip.to_dict() only carries recipient_id (no recipient_username) -- look it
// up on demand for the "sent" tab. Cheap: react-query dedupes/caches by id.
function RecipientLink({ userId }: { userId: string }) {
  const { data } = useQuery({
    queryKey: ["public-profile", userId],
    queryFn: () => getPublicProfile(userId),
  });
  return <Link to={`/users/${userId}`}>{data?.display_name ?? userId}</Link>;
}

export function Tips() {
  usePageTitle("チップ");
  const [tab, setTab] = useState<"received" | "sent">("received");

  const { data, isLoading } = useQuery({
    queryKey: ["tips", tab],
    queryFn: () => (tab === "received" ? tipService.getTipsReceived(50, 0) : tipService.getTipsSent(50, 0)),
  });

  return (
    <div>
      <h1>チップ</h1>
      <div className="filters-bar" role="tablist" aria-label="チップの表示切り替え" style={{ marginBottom: 16 }}>
        <button
          className={tab === "received" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "received"}
          onClick={() => setTab("received")}
        >
          受け取ったチップ
        </button>
        <button
          className={tab === "sent" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "sent"}
          onClick={() => setTab("sent")}
        >
          送ったチップ
        </button>
      </div>

      {isLoading ? (
        <CenterSpinner />
      ) : !data || data.items.length === 0 ? (
        <div className="empty-state">
          {tab === "received" ? "まだチップを受け取っていません。" : "まだチップを送ったことがありません。"}
        </div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {data.items.map((tip) => (
              <div key={tip.tip_id} className="row-item">
                <div>
                  <div style={{ fontWeight: 600 }}>
                    {tab === "received" ? (
                      tip.sender_username
                    ) : tip.recipient_id ? (
                      <RecipientLink userId={tip.recipient_id} />
                    ) : (
                      "-"
                    )}
                  </div>
                  {tip.message && <div style={{ fontSize: 13, color: "var(--muted)" }}>{tip.message}</div>}
                  <div style={{ fontSize: 12, color: "var(--faint)" }}>
                    {new Date(tip.created_at).toLocaleString("ja-JP")}
                  </div>
                </div>
                <span className="listing-price">{tip.amount.toLocaleString()} cr</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
