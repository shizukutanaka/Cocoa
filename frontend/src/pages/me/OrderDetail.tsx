import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getOrder } from "../../services/cartService";
import { CenterSpinner } from "../../components/Spinner";

export function OrderDetail() {
  const { orderId } = useParams<{ orderId: string }>();

  const { data: order, isLoading, isError } = useQuery({
    queryKey: ["order", orderId],
    queryFn: () => getOrder(orderId!),
    enabled: !!orderId,
  });

  if (isLoading) return <CenterSpinner />;
  if (isError || !order) return <div className="empty-state">注文が見つかりませんでした。</div>;

  return (
    <div>
      <p style={{ marginBottom: 8 }}>
        <Link to="/me/orders">← 注文履歴に戻る</Link>
      </p>
      <h1>注文詳細</h1>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="stat-value">
            <span className={order.status === "completed" ? "badge badge-success" : "badge"}>{order.status}</span>
          </div>
          <div className="stat-label">ステータス</div>
        </div>
        <div className="stat-tile">
          <div className="stat-value">{order.total_credits.toLocaleString()} cr</div>
          <div className="stat-label">合計金額</div>
        </div>
        <div className="stat-tile">
          <div className="stat-value">{new Date(order.created_at).toLocaleDateString("ja-JP")}</div>
          <div className="stat-label">購入日</div>
        </div>
      </div>

      {order.failure_reason && <div className="form-error-banner">{order.failure_reason}</div>}

      <div className="card card-pad">
        <div className="row-list">
          {order.items.map((item) => (
            <div key={item.listing_id} className="row-item">
              <div>
                <Link to={`/listings/${item.listing_id}`} style={{ fontWeight: 600 }}>
                  {item.name}
                </Link>
                <div style={{ fontSize: 13, color: "var(--muted)" }}>
                  {item.owner_username}
                  {item.promo_code && ` · プロモコード: ${item.promo_code}（${item.discount_percent}%引）`}
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                {item.discount_percent > 0 && (
                  <div style={{ fontSize: 13, color: "var(--faint)", textDecoration: "line-through" }}>
                    {item.unit_price.toLocaleString()} cr
                  </div>
                )}
                <span className="listing-price">{item.final_price.toLocaleString()} cr</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
