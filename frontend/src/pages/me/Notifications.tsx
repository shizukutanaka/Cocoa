import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as notificationsService from "../../services/notificationsService";
import { CenterSpinner } from "../../components/Spinner";

export function Notifications() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => notificationsService.listNotifications(false, 50, 0),
  });

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
