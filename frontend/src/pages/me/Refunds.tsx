import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import * as refundService from "../../services/refundService";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";

export function Refunds() {
  usePageTitle("払い戻しリクエスト");

  const { data, isLoading } = useQuery({
    queryKey: ["my-refunds"],
    queryFn: () => refundService.getMyRefunds(50, 0),
  });

  if (isLoading) return <CenterSpinner />;

  return (
    <div>
      <h1>払い戻しリクエスト</h1>
      {!data || data.items.length === 0 ? (
        <div className="empty-state">
          払い戻しリクエストはありません。注文詳細ページから申請できます。
        </div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {data.items.map((r) => (
              <div key={r.request_id} className="row-item" style={{ alignItems: "flex-start" }}>
                <div>
                  <Link to={`/me/orders/${r.order_id}`} style={{ fontWeight: 600 }}>
                    注文 {r.order_id.slice(0, 8)}
                  </Link>
                  <p style={{ fontSize: 13, color: "var(--muted)", margin: "4px 0 0" }}>{r.reason}</p>
                  <div style={{ fontSize: 12, color: "var(--faint)", marginTop: 2 }}>
                    {new Date(r.created_at).toLocaleDateString("ja-JP")} 申請
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span className="listing-price">{r.total_credits.toLocaleString()} cr</span>
                  {r.status === "pending" && <span className="badge badge-warning">審査中</span>}
                  {r.status === "approved" && <span className="badge badge-success">承認済み</span>}
                  {r.status === "rejected" && <span className="badge">却下</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
