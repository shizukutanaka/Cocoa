import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate } from "react-router-dom";
import * as adminService from "../../services/adminService";
import * as marketplaceService from "../../services/marketplaceService";
import * as userService from "../../services/userService";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";
import { apiErrorMessage } from "../../services/apiClient";
import type { ListingReport, ReviewReportRecord } from "../../types/api";

type Tab = "reports" | "review-reports" | "refunds";

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
  const [tab, setTab] = useState<Tab>("reports");

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
          className={tab === "refunds" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "refunds"}
          onClick={() => setTab("refunds")}
        >
          払い戻し申請
        </button>
      </div>

      {tab === "reports" && <ListingReportsTab />}
      {tab === "review-reports" && <ReviewReportsTab />}
      {tab === "refunds" && <RefundsTab />}
    </div>
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
                    <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
                      <ListingName listingId={r.listing_id} /> · 通報者{" "}
                      <ReporterName userId={r.reporter_id} /> ·{" "}
                      {new Date(r.created_at).toLocaleString("ja-JP")}
                    </div>
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
