import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as notificationsService from "../../services/notificationsService";
import { CenterSpinner } from "../../components/Spinner";
import { usePageTitle } from "../../hooks/usePageTitle";
import { useToast } from "../../hooks/useToast";
import { apiErrorMessage } from "../../services/apiClient";

// Mutable notification kinds (main/user_notifications.py NOTIFICATION_KINDS)
// with buyer/creator-facing Japanese labels. Kinds not listed here (e.g.
// system) stay always-on deliberately.
const MUTABLE_KINDS: Array<{ kind: string; label: string }> = [
  { kind: "new_follower", label: "新しいフォロワー" },
  { kind: "new_download", label: "自分の作品のダウンロード" },
  { kind: "new_review", label: "自分の作品への新しいレビュー" },
  { kind: "review_reply", label: "レビューへの返信" },
  { kind: "listing_published", label: "フォロー中クリエイターの新着" },
  { kind: "credit_gifted", label: "クレジットのギフト" },
  { kind: "tip_received", label: "チップの受け取り" },
  { kind: "price_drop", label: "ウィッシュリストの値下がり" },
  { kind: "back_in_stock", label: "ウィッシュリストの再入荷" },
  { kind: "saved_search_match", label: "保存した検索に一致する新着" },
];

export function Notifications() {
  usePageTitle("通知");
  const { show } = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => notificationsService.listNotifications(false, 50, 0),
  });

  const { data: mutedKinds } = useQuery({
    queryKey: ["muted-kinds"],
    queryFn: notificationsService.getMutedKinds,
  });

  async function handleToggleMute(kind: string) {
    const current = mutedKinds ?? [];
    const next = current.includes(kind) ? current.filter((k) => k !== kind) : [...current, kind];
    try {
      await notificationsService.setMutedKinds(next);
      queryClient.invalidateQueries({ queryKey: ["muted-kinds"] });
    } catch (err) {
      show(apiErrorMessage(err, "通知設定の更新に失敗しました"), "error");
    }
  }

  async function handleMarkRead(id: string) {
    await notificationsService.markRead(id);
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }

  async function handleMarkAllRead() {
    await notificationsService.markAllRead();
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }

  async function handleDelete(id: string) {
    await notificationsService.deleteNotification(id);
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }

  if (isLoading) return <CenterSpinner />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h1>通知</h1>
        {data && data.unread_count > 0 && (
          <button className="btn btn-secondary btn-sm" onClick={handleMarkAllRead}>
            全て既読にする
          </button>
        )}
      </div>

      <details style={{ marginBottom: 20 }}>
        <summary style={{ cursor: "pointer", fontWeight: 600, fontSize: 14 }}>通知設定</summary>
        <div className="card card-pad" style={{ marginTop: 10 }}>
          <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 0 }}>
            チェックを外した種類の通知は届かなくなります。
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 8 }}>
            {MUTABLE_KINDS.map(({ kind, label }) => (
              <label key={kind} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
                <input
                  type="checkbox"
                  checked={!(mutedKinds ?? []).includes(kind)}
                  onChange={() => handleToggleMute(kind)}
                />
                {label}
              </label>
            ))}
          </div>
        </div>
      </details>

      {!data || data.items.length === 0 ? (
        <div className="empty-state">通知はありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {data.items.map((n) => (
              <div key={n.notification_id} className={n.is_read ? "row-item" : "row-item unread"}>
                <div>
                  <div style={{ fontWeight: 600 }}>{n.title}</div>
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>{n.body}</div>
                  <div style={{ fontSize: 12, color: "var(--faint)" }}>{new Date(n.created_at).toLocaleString("ja-JP")}</div>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  {!n.is_read && (
                    <button className="btn btn-ghost btn-sm" onClick={() => handleMarkRead(n.notification_id)}>
                      既読
                    </button>
                  )}
                  <button className="btn btn-ghost btn-sm" onClick={() => handleDelete(n.notification_id)}>
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
