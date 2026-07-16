import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import * as commissionService from "../../services/commissionService";
import { apiErrorMessage } from "../../services/apiClient";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";
import type { CommissionRequest } from "../../types/api";

const STATUS_LABEL: Record<CommissionRequest["status"], string> = {
  pending: "承認待ち",
  accepted: "進行中",
  declined: "辞退",
  delivered: "納品済み",
  closed: "完了",
};

function statusBadge(status: CommissionRequest["status"]) {
  if (status === "accepted" || status === "delivered") return <span className="badge badge-success">{STATUS_LABEL[status]}</span>;
  if (status === "pending") return <span className="badge badge-warning">{STATUS_LABEL[status]}</span>;
  return <span className="badge">{STATUS_LABEL[status]}</span>;
}

function CommissionRow({ commission, role }: { commission: CommissionRequest; role: "creator" | "requester" }) {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [showRespondForm, setShowRespondForm] = useState(false);
  const [showDeliverForm, setShowDeliverForm] = useState(false);
  const [showDisputeForm, setShowDisputeForm] = useState(false);
  const [note, setNote] = useState("");
  const [deliveryNote, setDeliveryNote] = useState("");
  const [deliveryListingId, setDeliveryListingId] = useState("");
  const [disputeReason, setDisputeReason] = useState("");
  const [busy, setBusy] = useState(false);

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["commissions"] });
  }

  async function handleRespond(accept: boolean) {
    setBusy(true);
    try {
      await commissionService.respondToCommission(commission.request_id, accept, note);
      show(accept ? "コミッションを承認しました" : "コミッションを辞退しました");
      setShowRespondForm(false);
      setNote("");
      invalidate();
    } catch (err) {
      show(apiErrorMessage(err, "処理に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeliver() {
    if (!deliveryNote.trim()) return;
    setBusy(true);
    try {
      await commissionService.deliverCommission(commission.request_id, deliveryNote, deliveryListingId);
      show("納品しました");
      setShowDeliverForm(false);
      setDeliveryNote("");
      setDeliveryListingId("");
      invalidate();
    } catch (err) {
      show(apiErrorMessage(err, "納品に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleClose() {
    if (!window.confirm("このコミッションを完了としてクローズしますか？")) return;
    try {
      await commissionService.closeCommission(commission.request_id);
      show("クローズしました");
      invalidate();
    } catch (err) {
      show(apiErrorMessage(err, "クローズに失敗しました"), "error");
    }
  }

  async function handleDispute() {
    if (!disputeReason.trim()) return;
    setBusy(true);
    try {
      await commissionService.disputeCommission(commission.request_id, disputeReason);
      show("運営に報告しました");
      setShowDisputeForm(false);
      setDisputeReason("");
    } catch (err) {
      show(apiErrorMessage(err, "報告に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  const canDispute = commission.status === "accepted" || commission.status === "delivered";

  return (
    <div className="row-item" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontWeight: 600 }}>{commission.title}</div>
          <div style={{ fontSize: 13, color: "var(--muted)" }}>
            {role === "creator" ? `依頼者: ${commission.requester_username}` : "あなたの依頼"}
            {commission.budget_credits > 0 && ` · 予算 ${commission.budget_credits.toLocaleString()} cr`}
          </div>
        </div>
        {statusBadge(commission.status)}
      </div>

      <p style={{ fontSize: 14, margin: 0 }}>{commission.description}</p>

      {commission.creator_note && (
        <p style={{ fontSize: 13, color: "var(--muted)", margin: 0 }}>
          クリエイターより: {commission.creator_note}
        </p>
      )}
      {commission.delivery_note && (
        <p style={{ fontSize: 13, color: "var(--muted)", margin: 0 }}>
          納品メッセージ: {commission.delivery_note}
        </p>
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {role === "creator" && commission.status === "pending" && !showRespondForm && (
          <button className="btn btn-secondary btn-sm" onClick={() => setShowRespondForm(true)}>
            承認/辞退する
          </button>
        )}
        {role === "creator" && commission.status === "accepted" && !showDeliverForm && (
          <button className="btn btn-secondary btn-sm" onClick={() => setShowDeliverForm(true)}>
            納品する
          </button>
        )}
        {role === "requester" && commission.status === "pending" && (
          <button className="btn btn-ghost btn-sm" onClick={handleClose}>
            依頼を取り消す
          </button>
        )}
        {role === "requester" && commission.status === "delivered" && (
          <button className="btn btn-primary btn-sm" onClick={handleClose}>
            受領してクローズ
          </button>
        )}
        {canDispute && !showDisputeForm && (
          <button className="btn btn-ghost btn-sm" onClick={() => setShowDisputeForm(true)}>
            問題を報告
          </button>
        )}
      </div>

      {showRespondForm && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="メッセージ（任意）"
            style={{ flex: 1, minWidth: 160, fontSize: 13, padding: "4px 8px" }}
            aria-label="承認/辞退メッセージ"
          />
          <button className="btn btn-primary btn-sm" onClick={() => handleRespond(true)} disabled={busy}>
            承認する
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => handleRespond(false)} disabled={busy}>
            辞退する
          </button>
        </div>
      )}

      {showDeliverForm && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <input
            type="text"
            value={deliveryNote}
            onChange={(e) => setDeliveryNote(e.target.value)}
            placeholder="納品メッセージ"
            aria-label="納品メッセージ"
            style={{ fontSize: 13, padding: "4px 8px" }}
          />
          <input
            type="text"
            value={deliveryListingId}
            onChange={(e) => setDeliveryListingId(e.target.value)}
            placeholder="関連リスティングID（任意）"
            aria-label="関連リスティングID"
            style={{ fontSize: 13, padding: "4px 8px" }}
          />
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary btn-sm" onClick={handleDeliver} disabled={busy}>
              納品を確定
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowDeliverForm(false)}>
              キャンセル
            </button>
          </div>
        </div>
      )}

      {showDisputeForm && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input
            type="text"
            value={disputeReason}
            onChange={(e) => setDisputeReason(e.target.value)}
            placeholder="問題の内容"
            aria-label="問題の内容"
            style={{ flex: 1, minWidth: 160, fontSize: 13, padding: "4px 8px" }}
          />
          <button className="btn btn-secondary btn-sm" onClick={handleDispute} disabled={busy}>
            運営に報告
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => setShowDisputeForm(false)}>
            キャンセル
          </button>
        </div>
      )}
    </div>
  );
}

export function Commissions() {
  usePageTitle("コミッション");
  const [tab, setTab] = useState<"received" | "sent">("received");

  const { data, isLoading } = useQuery({
    queryKey: ["commissions", tab],
    queryFn: () =>
      tab === "received"
        ? commissionService.listCommissionsReceived(50, 0)
        : commissionService.listCommissionsSent(50, 0),
  });

  return (
    <div>
      <h1>コミッション</h1>
      <div className="filters-bar" role="tablist" aria-label="コミッションの表示切り替え" style={{ marginBottom: 16 }}>
        <button
          className={tab === "received" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "received"}
          onClick={() => setTab("received")}
        >
          受け取った依頼
        </button>
        <button
          className={tab === "sent" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "sent"}
          onClick={() => setTab("sent")}
        >
          自分の依頼
        </button>
      </div>

      {isLoading ? (
        <CenterSpinner />
      ) : !data || data.items.length === 0 ? (
        <div className="empty-state">
          {tab === "received" ? "受け取った依頼はありません。" : "まだコミッションを依頼したことがありません。"}
        </div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {data.items.map((c) => (
              <CommissionRow key={c.request_id} commission={c} role={tab === "received" ? "creator" : "requester"} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
