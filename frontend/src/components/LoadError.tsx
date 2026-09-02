import { apiErrorMessage } from "../services/apiClient";

/**
 * Shown when a list could not be loaded, instead of an empty state.
 *
 * A failed query leaves `data` undefined, and the pages here rendered
 * `!data || data.items.length === 0` as "you have nothing yet". So during an
 * outage a seller who owns listings was told 「まだ出品がありません」 with no
 * hint that anything was wrong (measured, audit #100).
 *
 * That is exactly the anti-pattern #47 removed from the server, where an
 * unavailable subsystem answered 200 with an empty list instead of 503. The
 * server was made honest; rendering its 503 as an empty state put the lie
 * back one layer up. apiErrorMessage already turns a 503 into
 * 「サービスが一時的に利用できません」, so the message the user sees is the
 * server's own reason where it gave one.
 */
export function LoadError({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div className="empty-state" role="alert">
      <div>{apiErrorMessage(error, "読み込みに失敗しました")}</div>
      {retry && (
        <button className="btn btn-secondary btn-sm" style={{ marginTop: 10 }} onClick={retry}>
          再試行
        </button>
      )}
    </div>
  );
}
