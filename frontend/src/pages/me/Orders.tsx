import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getOrders } from "../../services/cartService";
import { CenterSpinner } from "../../components/Spinner";

export function Orders() {
  const { data, isLoading } = useQuery({ queryKey: ["orders"], queryFn: () => getOrders(50, 0) });

  if (isLoading) return <CenterSpinner />;

  return (
    <div>
      <h1>注文履歴</h1>
      {!data || data.items.length === 0 ? (
        <div className="empty-state">まだ注文がありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {data.items.map((order) => (
              <Link
                key={order.order_id}
                to={`/me/orders/${order.order_id}`}
                className="row-item"
                style={{ color: "inherit", textDecoration: "none" }}
              >
                <div>
                  <div style={{ fontWeight: 600 }}>
                    {order.items.map((i) => i.name).join(", ") || "(アイテムなし)"}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>
                    {new Date(order.created_at).toLocaleString("ja-JP")} ·{" "}
                    <span className={order.status === "completed" || order.status === "success" ? "badge badge-success" : "badge"}>
                      {order.status}
                    </span>
                  </div>
                </div>
                <span className="listing-price">{order.total_credits.toLocaleString()} cr</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
