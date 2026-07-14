import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { getOrder } from "../../services/cartService";
import * as refundService from "../../services/refundService";
import { apiErrorMessage } from "../../services/apiClient";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";

export function OrderDetail() {
  const { orderId } = useParams<{ orderId: string }>();
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [showRefundForm, setShowRefundForm] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const { data: order, isLoading, isError } = useQuery({
    queryKey: ["order", orderId],
    queryFn: () => getOrder(orderId!),
    enabled: !!orderId,
  });

  usePageTitle("注文詳細");

  const { data: myRefunds } = useQuery({
    queryKey: ["my-refunds"],
    queryFn: () => refundService.getMyRefunds(200, 0),
  });

  const existingRequest = myRefunds?.items.find((r) => r.order_id === orderId);

  async function handleSubmitRefund(e: FormEvent) {
    e.preventDefault();
    if (!orderId || !reason.trim()) return;
    setBusy(true);
    try {
      await refundService.requestRefund(orderId, reason);
      show("払い戻しを申請しました");
      setShowRefundForm(false);
      setReason("");
      queryClient.invalidateQueries({ queryKey: ["my-refunds"] });
    } catch (err) {
      show(apiErrorMessage(err, "払い戻しの申請に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

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

      {order.status === "completed" && (
        <div style={{ marginTop: 20 }}>
          {existingRequest ? (
            <div className="card card-pad" style={{ maxWidth: 480 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <strong>払い戻しリクエスト</strong>
                {existingRequest.status === "pending" && <span className="badge badge-warning">審査中</span>}
                {existingRequest.status === "approved" && <span className="badge badge-success">承認済み</span>}
                {existingRequest.status === "rejected" && <span className="badge">却下</span>}
              </div>
              <p style={{ fontSize: 13, color: "var(--muted)", margin: 0 }}>{existingRequest.reason}</p>
              {existingRequest.admin_notes && (
                <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 6 }}>
                  運営コメント: {existingRequest.admin_notes}
                </p>
              )}
            </div>
          ) : showRefundForm ? (
            <form onSubmit={handleSubmitRefund} className="card card-pad" style={{ maxWidth: 480 }}>
              <div className="field">
                <label htmlFor="refund-reason">払い戻し理由</label>
                <textarea
                  id="refund-reason"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={3}
                  maxLength={1000}
                  required
                />
              </div>
              <div style={{ fontSize: 12, color: "var(--faint)", marginBottom: 10 }}>
                購入から72時間以内の注文のみ申請できます。
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
                  {busy ? "送信中..." : "申請する"}
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowRefundForm(false)}>
                  キャンセル
                </button>
              </div>
            </form>
          ) : (
            <button className="btn btn-secondary btn-sm" onClick={() => setShowRefundForm(true)}>
              払い戻しを申請する
            </button>
          )}
        </div>
      )}
    </div>
  );
}
