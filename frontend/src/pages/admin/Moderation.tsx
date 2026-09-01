import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate } from "react-router-dom";
import * as adminService from "../../services/adminService";
import * as marketplaceService from "../../services/marketplaceService";
import * as userService from "../../services/userService";
import { isSafeHttpUrl } from "../../utils/url";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";
import { apiErrorMessage } from "../../services/apiClient";
import type { AdminUser, ListingReport, ReviewReportRecord } from "../../types/api";

type Tab =
  | "overview"
  | "reports"
  | "review-reports"
  | "commission-disputes"
  | "refunds"
  | "creator-applications"
  | "users"
  | "banned";

const REASON_LABEL: Record<string, string> = {
  inappropriate: "不適切なコンテンツ",
  spam: "スパム",
  copyright: "著作権侵害",
  misleading: "誤解を招く説明",
  malware: "マルウェアの疑い",
  offensive: "不快な内容",
  false_info: "誤った情報",
  other: "その他",
};

export function AdminModeration() {
  usePageTitle("モデレーション");
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>("overview");
  // Ban management requires the admin role specifically (auth_manager
  // require_role("admin")); moderators would 403, so only admins see the tab.
  const isAdmin = user?.role === "admin";

  // The server enforces this on every endpoint; this check only avoids showing
  // a console that would 403 on every call.
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin" && user.role !== "moderator") {
    return <div className="empty-state">この画面は管理者・モデレーター専用です。</div>;
  }

  return (
    <div>
      <h1>モデレーション</h1>
      <p className="subhead">
        通報の裁定と払い戻しの承認を行います。取り下げは後から復元できます。
      </p>

      <div className="filters-bar" role="tablist" aria-label="モデレーションの表示切り替え" style={{ marginBottom: 16 }}>
        <button
          className={tab === "overview" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "overview"}
          onClick={() => setTab("overview")}
        >
          概要
        </button>
        <button
          className={tab === "reports" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "reports"}
          onClick={() => setTab("reports")}
        >
          出品の通報
        </button>
        <button
          className={tab === "review-reports" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "review-reports"}
          onClick={() => setTab("review-reports")}
        >
          レビューの通報
        </button>
        <button
          className={tab === "commission-disputes" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "commission-disputes"}
          onClick={() => setTab("commission-disputes")}
        >
          コミッション紛争
        </button>
        <button
          className={tab === "refunds" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "refunds"}
          onClick={() => setTab("refunds")}
        >
          払い戻し申請
        </button>
        <button
          className={tab === "creator-applications" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "creator-applications"}
          onClick={() => setTab("creator-applications")}
        >
          クリエイター認定申請
        </button>
        <button
          className={tab === "users" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "users"}
          onClick={() => setTab("users")}
        >
          ユーザー
        </button>
        {isAdmin && (
          <button
            className={tab === "banned" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
            role="tab"
            aria-selected={tab === "banned"}
            onClick={() => setTab("banned")}
          >
            停止中ユーザー
          </button>
        )}
      </div>

      {tab === "overview" && <OverviewTab />}
      {tab === "reports" && <ListingReportsTab />}
      {tab === "review-reports" && <ReviewReportsTab />}
      {tab === "commission-disputes" && <CommissionDisputesTab />}
      {tab === "refunds" && <RefundsTab />}
      {tab === "creator-applications" && <CreatorApplicationsTab />}
      {tab === "users" && <UsersTab />}
      {tab === "banned" && isAdmin && <BannedUsersTab />}
    </div>
  );
}

const PRIORITY_LABEL: Record<string, string> = { high: "高", medium: "中", low: "低" };
const MOD_STATUS_LABEL: Record<string, string> = {
  pending: "未処理",
  in_review: "確認中",
  resolved: "解決済み",
  dismissed: "却下",
};

/**
 * Commission disputes -- the one moderation-queue kind with no other home.
 *
 * The queue also mirrors listing reports, review reports and creator
 * applications, but each of those already has a dedicated tab; rendering the
 * whole queue would show every item twice. `commission_dispute` is enqueued
 * only by the commission "report a problem" flow (#31), so before this tab a
 * dispute over paid work sat in the queue with no way to adjudicate it -- the
 * same dead end #46 fixed for listing reports.
 */
function CommissionDisputesTab() {
  const { show } = useToast();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["admin-commission-disputes"],
    queryFn: () => adminService.listModerationItems("commission_dispute"),
  });

  const items = data?.items ?? [];
  const pending = items.filter((i) => i.status === "pending" || i.status === "in_review");

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["admin-commission-disputes"] });
  }

  async function act(itemId: string, fn: () => Promise<unknown>, okMessage: string) {
    setBusy(itemId);
    try {
      await fn();
      show(okMessage);
      refresh();
    } catch (err) {
      show(apiErrorMessage(err, "操作に失敗しました"), "error");
    } finally {
      setBusy(null);
    }
  }

  async function resolve(itemId: string, status: "resolved" | "dismissed") {
    const note = (notes[itemId] ?? "").trim();
    // Same rule as the report queue (#46): a decision without a recorded
    // reason leaves the next moderator reconstructing it from nothing.
    if (!note) {
      show("判断の理由を入力してください", "error");
      return;
    }
    await act(
      itemId,
      () => adminService.updateModerationStatus(itemId, status, note),
      status === "resolved" ? "解決済みにしました" : "却下しました",
    );
    setNotes((prev) => ({ ...prev, [itemId]: "" }));
  }

  if (isLoading) return <CenterSpinner />;

  return (
    <>
      <QueueHealth
        pending={pending.length}
        oldest={pending.length ? pending[pending.length - 1].created_at : undefined}
      />
      <p className="subhead" style={{ marginTop: -8 }}>
        受注制作の当事者が申し立てた紛争です。実際の作業内容・納品物の確認が必要なため、
        判断の理由を必ず記録してください。
      </p>

      {items.length === 0 ? (
        <div className="empty-state">コミッション紛争はありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {items.map((item) => (
              <div
                key={item.item_id}
                className="row-item"
                style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <div>
                    <div style={{ fontWeight: 600 }}>
                      {item.reason}
                      <span
                        className={item.priority === "high" ? "badge badge-warning" : "badge"}
                        style={{ marginLeft: 8 }}
                      >
                        優先度: {PRIORITY_LABEL[item.priority] ?? item.priority}
                      </span>
                      <span className="badge" style={{ marginLeft: 6 }}>
                        {MOD_STATUS_LABEL[item.status] ?? item.status}
                      </span>
                    </div>
                    {item.details && (
                      <div style={{ fontSize: 13, marginTop: 4, whiteSpace: "pre-wrap" }}>
                        {item.details}
                      </div>
                    )}
                    <div style={{ fontSize: 12, color: "var(--faint)", marginTop: 4 }}>
                      申立日 {new Date(item.created_at).toLocaleString("ja-JP")}
                      {item.assigned_to && ` · 担当 ${item.assigned_to.slice(0, 8)}`}
                    </div>
                    <div style={{ fontSize: 12, marginTop: 2 }}>
                      <Link to={`/me/commissions`}>対象コミッション {item.subject_id.slice(0, 8)}</Link>
                    </div>
                    {item.notes && (
                      <div style={{ fontSize: 13, marginTop: 4, color: "var(--muted)" }}>
                        記録: {item.notes}
                      </div>
                    )}
                  </div>
                </div>

                {item.status !== "resolved" && item.status !== "dismissed" && (
                  <>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {item.priority !== "high" && (
                        <button
                          className="btn btn-ghost btn-sm"
                          disabled={busy === item.item_id}
                          onClick={() =>
                            act(
                              item.item_id,
                              () => adminService.setModerationPriority(item.item_id, "high"),
                              "優先度を高にしました",
                            )
                          }
                        >
                          優先度を上げる
                        </button>
                      )}
                      {user && item.assigned_to !== user.user_id && (
                        <button
                          className="btn btn-ghost btn-sm"
                          disabled={busy === item.item_id}
                          onClick={() =>
                            act(
                              item.item_id,
                              () => adminService.assignModerationItem(item.item_id, user.user_id),
                              "自分に割り当てました",
                            )
                          }
                        >
                          自分が担当する
                        </button>
                      )}
                      {item.status === "pending" && (
                        <button
                          className="btn btn-ghost btn-sm"
                          disabled={busy === item.item_id}
                          onClick={() =>
                            act(
                              item.item_id,
                              () => adminService.updateModerationStatus(item.item_id, "in_review"),
                              "確認中にしました",
                            )
                          }
                        >
                          確認中にする
                        </button>
                      )}
                    </div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <input
                        className="input"
                        placeholder="判断の理由（必須・記録されます）"
                        value={notes[item.item_id] ?? ""}
                        onChange={(e) =>
                          setNotes((prev) => ({ ...prev, [item.item_id]: e.target.value }))
                        }
                        aria-label="判断の理由"
                        style={{ flex: 1, minWidth: 220 }}
                      />
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={busy === item.item_id}
                        onClick={() => resolve(item.item_id, "resolved")}
                      >
                        解決済みにする
                      </button>
                      <button
                        className="btn btn-secondary btn-sm"
                        disabled={busy === item.item_id}
                        onClick={() => resolve(item.item_id, "dismissed")}
                      >
                        却下する
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

const ROLE_STAT_LABEL: Record<string, string> = {
  admin: "管理者",
  moderator: "モデレーター",
  user: "一般",
};

/** Console landing: at-a-glance platform health from GET /api/admin/stats. */
function OverviewTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: () => adminService.getAdminStats(),
  });
  // The money question an operator actually needs answered: does every
  // balance still equal the sum of its ledger entries?
  const { data: integrity } = useQuery({
    queryKey: ["admin-ledger-integrity"],
    queryFn: () => adminService.getLedgerIntegrity(),
  });

  if (isLoading) return <CenterSpinner />;

  const u = data?.users;
  const m = data?.marketplace;

  return (
    <>
      {data?.durability && (
        <section style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>データの永続化</h2>
          <div className="card card-pad">
            {!data.durability.enabled ? (
              <div>
                <span className="badge badge-warning">無効</span>
                <span style={{ marginLeft: 8, fontSize: 13, color: "var(--muted)" }}>
                  完全インメモリで動作中 — 再起動で全データが消えます（COCOA_STATE_DIR で有効化）。
                </span>
              </div>
            ) : data.durability.ok === false ? (
              <div>
                <span className="badge badge-warning">⚠ 保存に失敗しています</span>
                <div style={{ fontSize: 13, marginTop: 6, whiteSpace: "pre-wrap" }}>
                  {data.durability.error}
                </div>
                <div style={{ fontSize: 13, marginTop: 4 }}>
                  このままプロセスが停止すると、最終成功
                  {data.durability.last_success_at
                    ? `（${new Date(data.durability.last_success_at).toLocaleString("ja-JP")}）`
                    : "（なし）"}
                  以降のデータを失います。
                </div>
              </div>
            ) : (
              <div>
                <span className="badge">✓ 保存中</span>
                <span style={{ marginLeft: 8, fontSize: 13, color: "var(--muted)" }}>
                  {data.durability.last_success_at
                    ? `最終保存 ${new Date(data.durability.last_success_at).toLocaleString("ja-JP")} · `
                    : "起動直後（初回保存待ち） · "}
                  {data.durability.interval_seconds}秒ごとに自動保存
                  {data.durability.stores_in_last_snapshot != null &&
                    ` · ${data.durability.stores_in_last_snapshot}ストア`}
                </span>
              </div>
            )}
          </div>
        </section>
      )}

      {integrity && (
        <section style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>クレジット台帳の整合性</h2>
          <div className="card card-pad">
            {integrity.consistent ? (
              <div>
                <span className="badge">✓ 整合</span>
                <span style={{ marginLeft: 8, fontSize: 13, color: "var(--muted)" }}>
                  {integrity.users_checked.toLocaleString()} 人の残高が台帳合計と一致しています。
                </span>
              </div>
            ) : (
              <div>
                <span className="badge badge-warning">⚠ 不整合 {integrity.discrepancy_count} 件</span>
                <div style={{ fontSize: 13, marginTop: 6 }}>
                  残高が台帳合計と一致しないユーザーがいます。金銭プリミティブを経由しない
                  変更か、復元された状態の破損が疑われます。
                </div>
                <div className="row-list" style={{ marginTop: 8 }}>
                  {integrity.discrepancies.slice(0, 10).map((d) => (
                    <div key={d.user_id} className="row-item">
                      <Link to={`/users/${d.user_id}`}>{d.user_id.slice(0, 12)}</Link>
                      <span style={{ fontSize: 13 }}>
                        残高 {d.balance.toLocaleString()} / 台帳 {d.ledger_sum.toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 16, marginBottom: 8 }}>ユーザー</h2>
        {u ? (
          <div className="stat-row">
            <div className="stat-tile">
              <div className="stat-value">{u.total.toLocaleString()}</div>
              <div className="stat-label">登録ユーザー</div>
            </div>
            <div className="stat-tile">
              <div className="stat-value">{u.active.toLocaleString()}</div>
              <div className="stat-label">有効</div>
            </div>
            <div className="stat-tile">
              <div className="stat-value">{u.locked.toLocaleString()}</div>
              <div className="stat-label">ロック中</div>
            </div>
            {Object.entries(u.by_role)
              .filter(([, n]) => n > 0)
              .map(([role, n]) => (
                <div className="stat-tile" key={role}>
                  <div className="stat-value">{n.toLocaleString()}</div>
                  <div className="stat-label">{ROLE_STAT_LABEL[role] ?? role}</div>
                </div>
              ))}
          </div>
        ) : (
          <div className="empty-state">ユーザー統計は利用できません。</div>
        )}
      </section>

      <section>
        <h2 style={{ fontSize: 16, marginBottom: 8 }}>マーケットプレイス</h2>
        {m ? (
          <div className="stat-row">
            <div className="stat-tile">
              <div className="stat-value">{m.total_listings.toLocaleString()}</div>
              <div className="stat-label">公開中の出品</div>
            </div>
            <div className="stat-tile">
              <div className="stat-value">{m.total_downloads.toLocaleString()}</div>
              <div className="stat-label">総ダウンロード</div>
            </div>
            <div className="stat-tile">
              <div className="stat-value">{m.total_ratings.toLocaleString()}</div>
              <div className="stat-label">総評価数</div>
            </div>
            <div className="stat-tile">
              <div className="stat-value">{m.categories.length.toLocaleString()}</div>
              <div className="stat-label">カテゴリ数</div>
            </div>
          </div>
        ) : (
          <div className="empty-state">マーケットプレイス統計は利用できません。</div>
        )}
      </section>
    </>
  );
}

/** Queue-health line: depth and the age of the oldest pending item. */
function QueueHealth({ pending, oldest }: { pending: number; oldest?: string }) {
  const ageHours = oldest
    ? Math.floor((Date.now() - new Date(oldest).getTime()) / 3_600_000)
    : null;
  return (
    <div className="stat-row" style={{ marginBottom: 16 }}>
      <div className="stat-tile">
        <div className="stat-value">{pending}</div>
        <div className="stat-label">未処理</div>
      </div>
      <div className="stat-tile">
        <div className="stat-value">{ageHours === null ? "-" : `${ageHours}h`}</div>
        <div className="stat-label">最古の未処理</div>
      </div>
    </div>
  );
}

function ListingReportsTab() {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["admin-reports", "pending"],
    queryFn: () => adminService.listReports("pending"),
  });

  // How many pending reports target each listing. Acting on a lone report is
  // the documented way competitors weaponise reporting, so the count is shown
  // next to every row.
  const countsByListing = useMemo(() => {
    const m: Record<string, number> = {};
    for (const r of data?.items ?? []) m[r.listing_id] = (m[r.listing_id] ?? 0) + 1;
    return m;
  }, [data]);

  // Highest-risk first, then oldest first within the same severity.
  const sorted = useMemo(() => {
    return [...(data?.items ?? [])].sort((a, b) => {
      const s = adminService.severityOf(a.reason) - adminService.severityOf(b.reason);
      return s !== 0 ? s : a.created_at.localeCompare(b.created_at);
    });
  }, [data]);

  async function resolve(r: ListingReport, action: "resolved" | "dismissed", takedown: boolean) {
    const note = (notes[r.report_id] ?? "").trim();
    // Every decision is recorded with a reason so the next moderator can see
    // why, rather than reconstructing it.
    if (!note) {
      show("判断の理由を入力してください（監査記録に残ります）", "error");
      return;
    }
    if (takedown && !confirm(`「${r.listing_id}」を取り下げます。よろしいですか？（後から復元できます）`)) return;
    setBusy(r.report_id);
    try {
      await adminService.resolveReport(r.report_id, action, note, takedown);
      show(takedown ? "取り下げて解決しました" : action === "resolved" ? "解決しました" : "却下しました");
      queryClient.invalidateQueries({ queryKey: ["admin-reports"] });
    } catch (err) {
      show(apiErrorMessage(err, "処理に失敗しました"), "error");
    } finally {
      setBusy(null);
    }
  }

  if (isLoading) return <CenterSpinner />;

  return (
    <>
      <QueueHealth pending={sorted.length} oldest={sorted[sorted.length - 1]?.created_at} />
      {sorted.length === 0 ? (
        <div className="empty-state">未処理の通報はありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {sorted.map((r) => (
              <div key={r.report_id} className="row-item" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                  <div>
                    <span className={adminService.severityOf(r.reason) <= 1 ? "badge badge-warning" : "badge"}>
                      {adminService.SEVERITY_LABEL[adminService.severityOf(r.reason)]}
                    </span>{" "}
                    <strong>{REASON_LABEL[r.reason] ?? r.reason}</strong>
                    {countsByListing[r.listing_id] > 1 && (
                      <span className="badge badge-warning" style={{ marginLeft: 8 }}>
                        同一出品に {countsByListing[r.listing_id]} 件
                      </span>
                    )}
                    <EditedSinceReport listingId={r.listing_id} reportedAt={r.created_at} />
                    <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
                      {r.listing_name ? (
                        <Link to={`/listings/${r.listing_id}`}>
                          {r.listing_name}
                          {r.listing_is_active === false && "（取り下げ済み）"}
                        </Link>
                      ) : (
                        <ListingName listingId={r.listing_id} />
                      )}
                      {r.owner_username && (
                        <>
                          {" · 出品者 "}
                          <Link to={`/users/${r.owner_id}`}>{r.owner_username}</Link>
                        </>
                      )}
                      {" · 通報者 "}
                      <ReporterName userId={r.reporter_id} /> ·{" "}
                      {new Date(r.created_at).toLocaleString("ja-JP")}
                    </div>
                    <SellerRecord report={r} />
                    {r.details && (
                      <div style={{ fontSize: 13, marginTop: 6, whiteSpace: "pre-wrap" }}>{r.details}</div>
                    )}
                  </div>
                </div>
                <input
                  aria-label="判断の理由"
                  placeholder="判断の理由（必須・監査記録に残ります）"
                  value={notes[r.report_id] ?? ""}
                  onChange={(e) => setNotes((n) => ({ ...n, [r.report_id]: e.target.value }))}
                />
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={busy === r.report_id}
                    onClick={() => resolve(r, "dismissed", false)}
                  >
                    問題なし（却下）
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={busy === r.report_id}
                    onClick={() => resolve(r, "resolved", false)}
                  >
                    対応済みにする
                  </button>
                  <button
                    className="btn btn-danger btn-sm"
                    disabled={busy === r.report_id}
                    onClick={() => resolve(r, "resolved", true)}
                  >
                    取り下げる
                  </button>
                  <RestoreButton listingId={r.listing_id} />
                  {r.owner_id && (
                    <BanSellerButton
                      ownerId={r.owner_id}
                      ownerName={r.owner_username ?? r.owner_id}
                      upheld={r.owner_history?.upheld_total ?? 0}
                    />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function ReviewReportsTab() {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["admin-review-reports", "pending"],
    queryFn: () => adminService.listReviewReports("pending"),
  });

  const sorted = useMemo(() => {
    return [...(data?.items ?? [])].sort((a, b) => {
      const s = adminService.severityOf(a.reason) - adminService.severityOf(b.reason);
      return s !== 0 ? s : a.created_at.localeCompare(b.created_at);
    });
  }, [data]);

  async function resolve(r: ReviewReportRecord, action: "resolved" | "dismissed", hide: boolean) {
    const note = (notes[r.report_id] ?? "").trim();
    if (!note) {
      show("判断の理由を入力してください（監査記録に残ります）", "error");
      return;
    }
    setBusy(r.report_id);
    try {
      await adminService.resolveReviewReport(r.report_id, action, note, hide);
      show(hide ? "レビューを非表示にしました" : "処理しました");
      queryClient.invalidateQueries({ queryKey: ["admin-review-reports"] });
    } catch (err) {
      show(apiErrorMessage(err, "処理に失敗しました"), "error");
    } finally {
      setBusy(null);
    }
  }

  if (isLoading) return <CenterSpinner />;

  return (
    <>
      <QueueHealth pending={sorted.length} oldest={sorted[sorted.length - 1]?.created_at} />
      {sorted.length === 0 ? (
        <div className="empty-state">未処理のレビュー通報はありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {sorted.map((r) => (
              <div key={r.report_id} className="row-item" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
                <div>
                  <strong>{REASON_LABEL[r.reason] ?? r.reason}</strong>
                  <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
                    レビュー {r.review_id} · 通報者 <ReporterName userId={r.reporter_id} /> ·{" "}
                    {new Date(r.created_at).toLocaleString("ja-JP")}
                  </div>
                  {r.details && (
                    <div style={{ fontSize: 13, marginTop: 6, whiteSpace: "pre-wrap" }}>{r.details}</div>
                  )}
                </div>
                <input
                  aria-label="判断の理由"
                  placeholder="判断の理由（必須・監査記録に残ります）"
                  value={notes[r.report_id] ?? ""}
                  onChange={(e) => setNotes((n) => ({ ...n, [r.report_id]: e.target.value }))}
                />
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={busy === r.report_id}
                    onClick={() => resolve(r, "dismissed", false)}
                  >
                    問題なし（却下）
                  </button>
                  <button
                    className="btn btn-danger btn-sm"
                    disabled={busy === r.report_id}
                    onClick={() => resolve(r, "resolved", true)}
                  >
                    レビューを非表示にする
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function RefundsTab() {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["admin-refunds", "pending"],
    queryFn: () => adminService.listRefunds("pending"),
  });

  const items = data?.items ?? [];

  async function decide(requestId: string, approve: boolean) {
    if (approve && !confirm("この払い戻しを承認します。クレジットが買い手へ返還されます。")) return;
    const note = (notes[requestId] ?? "").trim();
    if (!approve && !note) {
      show("却下の理由を入力してください", "error");
      return;
    }
    setBusy(requestId);
    try {
      if (approve) {
        const res = await adminService.approveRefund(requestId);
        show(`承認しました（${res.credits_returned ?? 0} クレジット返還）`);
      } else {
        await adminService.rejectRefund(requestId, note);
        show("却下しました");
      }
      queryClient.invalidateQueries({ queryKey: ["admin-refunds"] });
    } catch (err) {
      show(apiErrorMessage(err, "処理に失敗しました"), "error");
    } finally {
      setBusy(null);
    }
  }

  if (isLoading) return <CenterSpinner />;

  return (
    <>
      <QueueHealth pending={items.length} oldest={items[items.length - 1]?.created_at} />
      {items.length === 0 ? (
        <div className="empty-state">未処理の払い戻し申請はありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {items.map((r) => (
              <div key={r.request_id} className="row-item" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
                <div>
                  <strong>{r.total_credits.toLocaleString()} クレジット</strong>
                  <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
                    注文 {r.order_id} · 申請者 <ReporterName userId={r.user_id} /> ·{" "}
                    {new Date(r.created_at).toLocaleString("ja-JP")}
                  </div>
                  {r.reason && (
                    <div style={{ fontSize: 13, marginTop: 6, whiteSpace: "pre-wrap" }}>{r.reason}</div>
                  )}
                </div>
                <input
                  aria-label="却下の理由"
                  placeholder="却下する場合は理由を入力"
                  value={notes[r.request_id] ?? ""}
                  onChange={(e) => setNotes((n) => ({ ...n, [r.request_id]: e.target.value }))}
                />
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    className="btn btn-primary btn-sm"
                    disabled={busy === r.request_id}
                    onClick={() => decide(r.request_id, true)}
                  >
                    承認して返金
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={busy === r.request_id}
                    onClick={() => decide(r.request_id, false)}
                  >
                    却下
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

/**
 * Creator verification applications. Users could apply, but nothing could ever
 * review the application, so every request sat pending forever and the verified
 * badge was ungrantable through the UI.
 *
 * What this review actually checks is a stated reason and a portfolio link --
 * not identity documents. Guidance on trust badges is explicit that a badge
 * should say what was checked, because a badge that implies more than the
 * evidence supports teaches buyers to discount every signal. The UI therefore
 * spells out the scope of the check for the reviewer, and the decision note is
 * mandatory so the basis of each approval is recorded.
 */
function CreatorApplicationsTab() {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["admin-creator-applications", "pending"],
    queryFn: () => adminService.listCreatorApplications("pending"),
  });

  const items = data?.items ?? [];

  async function decide(id: string, decision: "approved" | "rejected") {
    const note = (notes[id] ?? "").trim();
    if (!note) {
      show("確認した内容を入力してください（記録に残ります）", "error");
      return;
    }
    setBusy(id);
    try {
      await adminService.reviewCreatorApplication(id, decision, note);
      show(decision === "approved" ? "認定しました" : "却下しました");
      queryClient.invalidateQueries({ queryKey: ["admin-creator-applications"] });
    } catch (err) {
      show(apiErrorMessage(err, "処理に失敗しました"), "error");
    } finally {
      setBusy(null);
    }
  }

  if (isLoading) return <CenterSpinner />;

  return (
    <>
      <QueueHealth pending={items.length} oldest={items[items.length - 1]?.created_at} />
      <div className="card card-pad" style={{ marginBottom: 16, fontSize: 13, color: "var(--muted)" }}>
        この審査で確認できるのは<strong>申請理由とポートフォリオ</strong>のみです。本人確認・法人確認は含まれないため、
        認定バッジはその範囲を超える保証を意味しません。確認した内容を必ず記録してください。
      </div>
      {items.length === 0 ? (
        <div className="empty-state">未処理の認定申請はありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {items.map((a) => (
              <div key={a.application_id} className="row-item" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
                <div>
                  <strong>{a.username}</strong>
                  <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
                    申請日 {new Date(a.created_at).toLocaleString("ja-JP")}
                  </div>
                  {a.reason && (
                    <div style={{ fontSize: 13, marginTop: 6, whiteSpace: "pre-wrap" }}>{a.reason}</div>
                  )}
                  {a.portfolio_url && isSafeHttpUrl(a.portfolio_url) ? (
                    <div style={{ marginTop: 6, fontSize: 13 }}>
                      <a href={a.portfolio_url} target="_blank" rel="noopener noreferrer">
                        ポートフォリオを開く
                      </a>
                    </div>
                  ) : a.portfolio_url ? (
                    <div style={{ marginTop: 6, fontSize: 13, color: "var(--faint)" }}>
                      ポートフォリオURLが不正です: {a.portfolio_url}
                    </div>
                  ) : null}
                </div>
                <input
                  aria-label="確認した内容"
                  placeholder="確認した内容（必須・記録に残ります）"
                  value={notes[a.application_id] ?? ""}
                  onChange={(e) => setNotes((n) => ({ ...n, [a.application_id]: e.target.value }))}
                />
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    className="btn btn-primary btn-sm"
                    disabled={busy === a.application_id}
                    onClick={() => decide(a.application_id, "approved")}
                  >
                    認定する
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={busy === a.application_id}
                    onClick={() => decide(a.application_id, "rejected")}
                  >
                    却下
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

/**
 * Banned users, with the reason and who banned them, and a one-click unban.
 * #50 added the ban action but no way to see or reverse a ban -- completing the
 * enforcement loop the same way takedowns became reversible (#45): an
 * enforcement action a moderator can't undo is a trap for mistakes.
 */
const ROLE_LABEL: Record<string, string> = {
  admin: "管理者",
  moderator: "モデレーター",
  user: "一般",
};

/**
 * User roster with search, credit grants, role changes and badge revocation.
 *
 * The whole roster comes back in one call (no server-side paging), so search
 * is client-side over username / email / id / role. Credit grant moves the
 * same in-app ledger that refunds use -- a support/comp tool, not real money.
 *
 * The tab itself stays open to moderators (roster + credit grant work for
 * them), but role changes and badge revocation are admin-only server-side, so
 * those controls are wrapped in isAdmin -- the same mismatch the banned-users
 * tab already avoids by gating itself. A moderator would otherwise see buttons
 * that always 403.
 */
function UsersTab() {
  const { show } = useToast();
  const { user: me } = useAuth();
  const isAdmin = me?.role === "admin";
  const queryClient = useQueryClient();
  const [q, setQ] = useState("");
  const [grantFor, setGrantFor] = useState<string | null>(null);
  const [amount, setAmount] = useState("");
  const [quotaFor, setQuotaFor] = useState<string | null>(null);
  const [quotaValue, setQuotaValue] = useState("");
  const [busy, setBusy] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => adminService.listUsers(),
  });

  const users = useMemo(() => {
    const all = data?.users ?? [];
    const needle = q.trim().toLowerCase();
    if (!needle) return all;
    return all.filter(
      (u) =>
        u.username.toLowerCase().includes(needle) ||
        u.email.toLowerCase().includes(needle) ||
        u.user_id.toLowerCase().includes(needle) ||
        u.role.toLowerCase().includes(needle),
    );
  }, [data, q]);

  function openGrant(userId: string) {
    setGrantFor(userId);
    setAmount("");
  }

  function refreshRoster() {
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
  }

  async function applyRole(u: AdminUser, newRole: "user" | "moderator" | "admin") {
    if (newRole === u.role) return;
    if (!confirm(`「${u.username}」のロールを ${ROLE_LABEL[newRole] ?? newRole} に変更します。よろしいですか？`)) {
      return;
    }
    setBusy(true);
    try {
      await adminService.changeUserRole(u.user_id, newRole);
      show(`${u.username} を ${ROLE_LABEL[newRole] ?? newRole} にしました`);
      refreshRoster();
    } catch (err) {
      show(apiErrorMessage(err, "ロール変更に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function applyQuota(u: AdminUser, unlimited: boolean) {
    const value = unlimited ? -1 : Number(quotaValue);
    if (!unlimited && (!Number.isInteger(value) || value < 0)) {
      show("公開上限は0以上の整数で指定してください", "error");
      return;
    }
    setBusy(true);
    try {
      const res = await adminService.setListingQuota(u.user_id, value);
      show(
        res.max_listings === null
          ? `${u.username} の公開上限を解除しました`
          : `${u.username} の公開上限を ${res.max_listings} 件にしました（現在 ${res.current_active} 件公開中）`,
      );
      setQuotaFor(null);
      setQuotaValue("");
    } catch (err) {
      show(apiErrorMessage(err, "公開上限の設定に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function revokeBadge(u: AdminUser) {
    if (!confirm(`「${u.username}」のクリエイター認定を取り消します。よろしいですか？`)) return;
    setBusy(true);
    try {
      await adminService.revokeCreatorVerification(u.user_id);
      show(`${u.username} の認定を取り消しました`);
      refreshRoster();
    } catch (err) {
      show(apiErrorMessage(err, "認定の取り消しに失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function submitGrant(u: AdminUser) {
    const value = Number(amount);
    if (!Number.isInteger(value) || value < 1) {
      show("付与額は1以上の整数で指定してください", "error");
      return;
    }
    setBusy(true);
    try {
      const res = await adminService.grantCredits(u.user_id, value);
      show(`${u.username} に ${res.granted.toLocaleString()} クレジット付与しました（残高 ${res.new_balance.toLocaleString()}）`);
      setGrantFor(null);
      setAmount("");
    } catch (err) {
      show(apiErrorMessage(err, "クレジット付与に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) return <CenterSpinner />;

  return (
    <>
      <div className="stat-row" style={{ marginBottom: 16 }}>
        <div className="stat-tile">
          <div className="stat-value">{data?.total ?? 0}</div>
          <div className="stat-label">登録ユーザー</div>
        </div>
      </div>

      <div className="filters-bar" style={{ marginBottom: 16 }}>
        <input
          className="input"
          type="search"
          placeholder="ユーザー名・メール・ID・ロールで検索"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="ユーザー検索"
          style={{ maxWidth: 360 }}
        />
      </div>

      {users.length === 0 ? (
        <div className="empty-state">該当するユーザーはいません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {users.map((u) => (
              <div key={u.user_id} className="row-item" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                  <div>
                    <Link to={`/users/${u.user_id}`} style={{ fontWeight: 600 }}>
                      @{u.username}
                    </Link>
                    <span className="badge" style={{ marginLeft: 8 }}>{ROLE_LABEL[u.role] ?? u.role}</span>
                    {u.is_creator_verified && <span className="badge" style={{ marginLeft: 6 }}>✓ 認定クリエイター</span>}
                    {!u.is_active && <span className="badge badge-warning" style={{ marginLeft: 6 }}>停止中</span>}
                    {u.locked && <span className="badge badge-warning" style={{ marginLeft: 6 }}>ロック中</span>}
                    <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 2 }}>{u.email}</div>
                    <div style={{ fontSize: 12, color: "var(--faint)", marginTop: 2 }}>
                      登録 {new Date(u.created_at).toLocaleDateString("ja-JP")}
                      {u.last_login && ` · 最終ログイン ${new Date(u.last_login).toLocaleDateString("ja-JP")}`}
                      {u.failed_attempts > 0 && ` · 失敗 ${u.failed_attempts} 回`}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                    {grantFor !== u.user_id && (
                      <button className="btn btn-secondary btn-sm" onClick={() => openGrant(u.user_id)}>
                        クレジット付与
                      </button>
                    )}
                    {/* Role changes are admin-only server-side, and the server
                        refuses to change the caller's own role (an admin who
                        demotes themselves can never get back in -- #73), so
                        the control is hidden on your own row rather than
                        offering a button that always fails. */}
                    {isAdmin && u.user_id !== me?.user_id && (
                      <select
                        className="input"
                        value={u.role}
                        disabled={busy}
                        aria-label={`${u.username} のロール`}
                        onChange={(e) => applyRole(u, e.target.value as "user" | "moderator" | "admin")}
                        style={{ maxWidth: 160 }}
                      >
                        <option value="user">一般</option>
                        <option value="moderator">モデレーター</option>
                        <option value="admin">管理者</option>
                      </select>
                    )}
                    {isAdmin && u.is_creator_verified && (
                      <button
                        className="btn btn-ghost btn-sm"
                        disabled={busy}
                        onClick={() => revokeBadge(u)}
                      >
                        認定を取り消す
                      </button>
                    )}
                    {isAdmin && quotaFor !== u.user_id && (
                      <button
                        className="btn btn-ghost btn-sm"
                        disabled={busy}
                        onClick={() => { setQuotaFor(u.user_id); setQuotaValue(""); }}
                      >
                        公開上限
                      </button>
                    )}
                  </div>
                </div>
                {quotaFor === u.user_id && (
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>
                      出品を乱発する出品者への段階的な対応。BANより軽く、いつでも解除できます。
                    </span>
                    <input
                      className="input"
                      type="number"
                      min={0}
                      step={1}
                      placeholder="公開できる最大件数"
                      value={quotaValue}
                      onChange={(e) => setQuotaValue(e.target.value)}
                      aria-label={`${u.username} の公開上限`}
                      style={{ maxWidth: 200 }}
                    />
                    <button className="btn btn-primary btn-sm" disabled={busy}
                            onClick={() => applyQuota(u, false)}>
                      上限を設定
                    </button>
                    <button className="btn btn-secondary btn-sm" disabled={busy}
                            onClick={() => applyQuota(u, true)}>
                      上限を解除
                    </button>
                    <button className="btn btn-ghost btn-sm" disabled={busy}
                            onClick={() => { setQuotaFor(null); setQuotaValue(""); }}>
                      キャンセル
                    </button>
                  </div>
                )}
                {grantFor === u.user_id && (
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <input
                      className="input"
                      type="number"
                      min={1}
                      step={1}
                      placeholder="付与するクレジット数"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      aria-label={`${u.username} への付与クレジット数`}
                      style={{ maxWidth: 220 }}
                    />
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => submitGrant(u)}
                      disabled={busy}
                    >
                      付与する
                    </button>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => { setGrantFor(null); setAmount(""); }}
                      disabled={busy}
                    >
                      キャンセル
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function BannedUsersTab() {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-banned-users"],
    queryFn: () => adminService.listBannedUsers(),
  });

  const items = data?.items ?? [];

  async function handleUnban(userId: string, username: string) {
    if (!confirm(`「${username}」の停止を解除します。よろしいですか？`)) return;
    setBusy(userId);
    try {
      await adminService.unbanUser(userId);
      show(`${username} の停止を解除しました`);
      queryClient.invalidateQueries({ queryKey: ["admin-banned-users"] });
    } catch (err) {
      show(apiErrorMessage(err, "停止解除に失敗しました"), "error");
    } finally {
      setBusy(null);
    }
  }

  if (isLoading) return <CenterSpinner />;

  return (
    <>
      <div className="stat-row" style={{ marginBottom: 16 }}>
        <div className="stat-tile">
          <div className="stat-value">{data?.total ?? 0}</div>
          <div className="stat-label">停止中</div>
        </div>
      </div>
      {items.length === 0 ? (
        <div className="empty-state">停止中のユーザーはいません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {items.map((u) => (
              <div key={u.user_id} className="row-item">
                <div>
                  <Link to={`/users/${u.user_id}`} style={{ fontWeight: 600 }}>
                    {u.display_name || u.username}
                  </Link>
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>
                    @{u.username}
                    {u.banned_at && ` · ${new Date(u.banned_at).toLocaleString("ja-JP")}`}
                  </div>
                  {u.ban_reason && (
                    <div style={{ fontSize: 13, marginTop: 4, whiteSpace: "pre-wrap" }}>
                      理由: {u.ban_reason}
                    </div>
                  )}
                </div>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleUnban(u.user_id, u.username)}
                  disabled={busy === u.user_id}
                >
                  停止を解除
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

/** Reports carry only ids, so resolve names on demand (shared query cache). */
function ListingName({ listingId }: { listingId: string }) {
  const { data } = useQuery({
    queryKey: ["listing", listingId],
    queryFn: () => marketplaceService.getListing(listingId),
  });
  if (!data) return <span>出品 {listingId.slice(0, 8)}</span>;
  return (
    <Link to={`/listings/${listingId}`}>
      {data.name}
      {!data.is_active && "（取り下げ済み）"}
    </Link>
  );
}

/**
 * The seller's standing record, shown on every report.
 *
 * Enforcement guidance is consistent that repeat offenders only become visible
 * when a seller's history is considered rather than each report in isolation --
 * removing one listing does nothing about an account that simply publishes
 * again. `upheld` counts only reports a moderator actioned, so reports that
 * were thrown out never accumulate against the seller.
 */
function SellerRecord({ report }: { report: ListingReport }) {
  const h = report.owner_history;
  if (!h || h.reports_total <= 1) return null;
  const repeat = h.upheld_total >= 2;
  return (
    <div style={{ fontSize: 13, marginTop: 4 }}>
      <span className={repeat ? "badge badge-warning" : "badge"}>
        この出品者: 通報 {h.reports_total} 件 / 是認 {h.upheld_total} 件
      </span>
      {repeat && (
        <span style={{ marginLeft: 8, color: "var(--muted)" }}>
          複数回の違反が確認されています。アカウント単位の対応を検討してください。
        </span>
      )}
    </div>
  );
}

/** Escalate from the listing to the account once the record justifies it. */
function BanSellerButton({
  ownerId,
  ownerName,
  upheld,
}: {
  ownerId: string;
  ownerName: string;
  upheld: number;
}) {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);

  async function handleBan() {
    const reason = window.prompt(
      `「${ownerName}」のアカウントを停止します。\n是認済みの違反: ${upheld} 件\n\n停止の理由を入力してください（記録に残ります）`,
      "",
    );
    if (reason === null) return;
    if (!reason.trim()) {
      show("停止の理由を入力してください", "error");
      return;
    }
    setBusy(true);
    try {
      await adminService.banUser(ownerId, reason.trim());
      show(`${ownerName} のアカウントを停止しました`);
      queryClient.invalidateQueries({ queryKey: ["admin-reports"] });
    } catch (err) {
      show(apiErrorMessage(err, "アカウント停止に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <button className="btn btn-ghost btn-sm" onClick={handleBan} disabled={busy}>
      出品者を停止
    </button>
  );
}

/**
 * Warn when a listing changed after it was reported.
 *
 * Sellers can edit a published listing, so the content a moderator sees may no
 * longer be the content that was reported -- the classic way to dodge review.
 * This is deliberately a signal rather than an edit lock: freezing a listing on
 * any pending report would let a competitor disable a rival by reporting it.
 */
function EditedSinceReport({ listingId, reportedAt }: { listingId: string; reportedAt: string }) {
  const { data } = useQuery({
    queryKey: ["listing", listingId],
    queryFn: () => marketplaceService.getListing(listingId),
  });
  if (!data?.updated_at) return null;
  if (new Date(data.updated_at) <= new Date(reportedAt)) return null;
  return (
    <span className="badge badge-warning" style={{ marginLeft: 8 }} title="通報後に出品が編集されています">
      通報後に編集あり
    </span>
  );
}

function ReporterName({ userId }: { userId: string }) {
  const { data } = useQuery({
    queryKey: ["public-profile", userId],
    queryFn: () => userService.getPublicProfile(userId),
  });
  return <span>{data?.display_name ?? userId.slice(0, 8)}</span>;
}

/** Undo a takedown made in error. */
function RestoreButton({ listingId }: { listingId: string }) {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const { data: listing } = useQuery({
    queryKey: ["listing", listingId],
    queryFn: () => marketplaceService.getListing(listingId),
  });

  // Only meaningful once the listing is actually down.
  if (!listing || listing.is_active) return null;

  async function handleRestore() {
    setBusy(true);
    try {
      await adminService.restoreListing(listingId);
      show("復元しました");
      queryClient.invalidateQueries({ queryKey: ["listing", listingId] });
    } catch (err) {
      show(apiErrorMessage(err, "復元に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <button className="btn btn-ghost btn-sm" onClick={handleRestore} disabled={busy}>
      取り下げを取り消す
    </button>
  );
}
