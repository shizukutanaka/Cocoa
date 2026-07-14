import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import * as marketplaceService from "../../services/marketplaceService";
import * as authService from "../../services/authService";
import { apiErrorMessage } from "../../services/apiClient";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";

function topEntries(counts: Record<string, number>, limit = 5): Array<[string, number]> {
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit);
}

function AnalyticsSection() {
  const { data, isLoading } = useQuery({
    queryKey: ["creator-analytics"],
    queryFn: marketplaceService.getMyCreatorAnalytics,
  });

  if (isLoading) return <CenterSpinner />;
  if (!data) return null;

  return (
    <section style={{ marginBottom: 28 }}>
      <h2 style={{ fontSize: 18 }}>統計</h2>
      <div className="stat-row">
        <div className="stat-tile">
          <div className="stat-value">{data.active_listings}</div>
          <div className="stat-label">公開中（全{data.total_listings}件）</div>
        </div>
        <div className="stat-tile">
          <div className="stat-value">{data.total_downloads.toLocaleString()}</div>
          <div className="stat-label">総ダウンロード数</div>
        </div>
        <div className="stat-tile">
          <div className="stat-value">{data.total_credits_earned.toLocaleString()} cr</div>
          <div className="stat-label">累計売上</div>
        </div>
        <div className="stat-tile">
          <div className="stat-value">{data.total_reviews}</div>
          <div className="stat-label">レビュー数</div>
        </div>
      </div>

      {data.top_listing && (
        <p style={{ fontSize: 14, marginTop: 12 }}>
          人気No.1: <Link to={`/listings/${data.top_listing.listing_id}`}>{data.top_listing.name}</Link>
          {` (${data.top_listing.download_count.toLocaleString()} DL)`}
        </p>
      )}

      {(topEntries(data.downloads_by_tag).length > 0 || topEntries(data.downloads_by_category).length > 0) && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginTop: 16 }}>
          {topEntries(data.downloads_by_tag).length > 0 && (
            <div>
              <h3 style={{ fontSize: 14, color: "var(--muted)" }}>人気タグ（DL数）</h3>
              {topEntries(data.downloads_by_tag).map(([tag, count]) => (
                <div key={tag} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "3px 0" }}>
                  <span>{tag}</span>
                  <span style={{ color: "var(--muted)" }}>{count}</span>
                </div>
              ))}
            </div>
          )}
          {topEntries(data.downloads_by_category).length > 0 && (
            <div>
              <h3 style={{ fontSize: 14, color: "var(--muted)" }}>カテゴリ別（DL数）</h3>
              {topEntries(data.downloads_by_category).map(([cat, count]) => (
                <div key={cat} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "3px 0" }}>
                  <span>{cat}</span>
                  <span style={{ color: "var(--muted)" }}>{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function EarningsSection() {
  const [days, setDays] = useState(30);
  const { data, isLoading } = useQuery({
    queryKey: ["creator-earnings", days],
    queryFn: () => marketplaceService.getMyEarnings(days),
  });

  return (
    <section style={{ marginBottom: 28 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h2 style={{ fontSize: 18 }}>収益</h2>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))} style={{ fontSize: 13 }}>
          <option value={7}>過去7日間</option>
          <option value={30}>過去30日間</option>
          <option value={90}>過去90日間</option>
        </select>
      </div>
      {isLoading ? (
        <CenterSpinner />
      ) : data ? (
        <div className="stat-row">
          <div className="stat-tile">
            <div className="stat-value">{data.total_earned.toLocaleString()} cr</div>
            <div className="stat-label">合計収益</div>
          </div>
          <div className="stat-tile">
            <div className="stat-value">{data.sales.toLocaleString()} cr</div>
            <div className="stat-label">販売収益</div>
          </div>
          <div className="stat-tile">
            <div className="stat-value">{data.tips_and_gifts_received.toLocaleString()} cr</div>
            <div className="stat-label">チップ・ギフト</div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function CreatorApplicationSection() {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [portfolioUrl, setPortfolioUrl] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const { data: application, isLoading } = useQuery({
    queryKey: ["my-creator-application"],
    queryFn: authService.getMyCreatorApplication,
  });

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await authService.submitCreatorApplication(reason, portfolioUrl);
      setReason("");
      setPortfolioUrl("");
      queryClient.invalidateQueries({ queryKey: ["my-creator-application"] });
      show("クリエイター認定を申請しました");
    } catch (err) {
      setError(apiErrorMessage(err, "申請に失敗しました"));
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) return <CenterSpinner />;

  // A rejected application can be re-submitted; pending/approved show status only.
  const canApply = !application || application.status === "rejected";

  return (
    <section>
      <h2 style={{ fontSize: 18 }}>クリエイター認定</h2>
      <p style={{ color: "var(--muted)", fontSize: 14 }}>
        認定されると、プロフィールに認証バッジが表示されます。
      </p>

      {application && (
        <div className="card card-pad" style={{ maxWidth: 480, marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {application.status === "pending" && <span className="badge badge-warning">審査中</span>}
            {application.status === "approved" && <span className="badge badge-success">認定済み</span>}
            {application.status === "rejected" && <span className="badge">却下</span>}
            <span style={{ fontSize: 12, color: "var(--faint)" }}>
              {new Date(application.created_at).toLocaleDateString("ja-JP")} 申請
            </span>
          </div>
          <p style={{ fontSize: 13, margin: "6px 0 0" }}>{application.reason}</p>
          {application.review_note && (
            <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 6 }}>
              運営コメント: {application.review_note}
            </p>
          )}
        </div>
      )}

      {canApply && (
        <form onSubmit={handleSubmit} className="card card-pad" style={{ maxWidth: 480 }}>
          {error && <div className="form-error-banner">{error}</div>}
          <div className="field">
            <label htmlFor="application-reason">申請理由</label>
            <textarea
              id="application-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              maxLength={1000}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="application-portfolio">ポートフォリオURL（任意）</label>
            <input
              id="application-portfolio"
              value={portfolioUrl}
              onChange={(e) => setPortfolioUrl(e.target.value)}
              placeholder="https://..."
            />
          </div>
          <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "送信中..." : application ? "再申請する" : "申請する"}
          </button>
        </form>
      )}
    </section>
  );
}

export function CreatorDashboard() {
  usePageTitle("クリエイターダッシュボード");
  return (
    <div>
      <h1>クリエイターダッシュボード</h1>
      <AnalyticsSection />
      <EarningsSection />
      <CreatorApplicationSection />
    </div>
  );
}
