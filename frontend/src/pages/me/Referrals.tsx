import { useQuery } from "@tanstack/react-query";
import * as referralService from "../../services/referralService";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { CenterSpinner } from "../../components/Spinner";

export function Referrals() {
  usePageTitle("友達を招待");
  const { show } = useToast();

  const { data: myCode, isLoading: codeLoading } = useQuery({
    queryKey: ["referral-code"],
    queryFn: referralService.getMyCode,
  });

  const { data: stats } = useQuery({
    queryKey: ["referral-stats"],
    queryFn: referralService.getMyStats,
  });

  const { data: referrals } = useQuery({
    queryKey: ["referral-list"],
    queryFn: () => referralService.getMyReferrals(50, 0),
  });

  const inviteUrl = myCode?.code ? `${window.location.origin}/register?ref=${myCode.code}` : "";

  async function copy(textToCopy: string, label: string) {
    try {
      await navigator.clipboard.writeText(textToCopy);
      show(`${label}をコピーしました`);
    } catch {
      show("コピーに失敗しました", "error");
    }
  }

  if (codeLoading) return <CenterSpinner />;

  return (
    <div>
      <h1>友達を招待</h1>
      <p style={{ color: "var(--muted)", fontSize: 14 }}>
        招待した友達が初めて購入すると、あなたに50クレジットが付与されます。
      </p>

      <div className="card card-pad" style={{ marginBottom: 20 }}>
        <div className="field">
          <label>あなたの招待コード</label>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <code style={{ fontSize: 18, fontWeight: 700, letterSpacing: 1 }}>{myCode?.code || "—"}</code>
            {myCode?.code && (
              <button className="btn btn-secondary btn-sm" onClick={() => copy(myCode.code, "招待コード")}>
                コードをコピー
              </button>
            )}
          </div>
        </div>
        {inviteUrl && (
          <div className="field" style={{ marginBottom: 0 }}>
            <label>招待リンク</label>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <code style={{ fontSize: 13, wordBreak: "break-all" }}>{inviteUrl}</code>
              <button className="btn btn-secondary btn-sm" onClick={() => copy(inviteUrl, "招待リンク")}>
                リンクをコピー
              </button>
            </div>
          </div>
        )}
      </div>

      {stats && (
        <div className="stat-row" style={{ marginBottom: 20 }}>
          <div className="stat-tile">
            <div className="stat-value">{stats.total_referrals}</div>
            <div className="stat-label">招待した人数</div>
          </div>
          <div className="stat-tile">
            <div className="stat-value">{stats.converted}</div>
            <div className="stat-label">購入に至った人数</div>
          </div>
          <div className="stat-tile">
            <div className="stat-value">{stats.total_bonus_earned.toLocaleString()} cr</div>
            <div className="stat-label">獲得ボーナス</div>
          </div>
        </div>
      )}

      <h2 style={{ fontSize: 18 }}>招待履歴</h2>
      {!referrals || referrals.items.length === 0 ? (
        <div className="empty-state">まだ招待実績がありません。上のリンクを友達に共有しましょう。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {referrals.items.map((r) => (
              <div key={r.referral_id} className="row-item">
                <div>
                  <div style={{ fontSize: 14 }}>
                    {new Date(r.created_at).toLocaleDateString("ja-JP")} に登録
                  </div>
                  <div style={{ fontSize: 12, color: "var(--faint)" }}>ID: {r.referred_id}</div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  {r.status === "converted" ? (
                    <>
                      <span className="badge badge-success">購入済み</span>
                      <span className="listing-price">+{r.bonus_awarded} cr</span>
                    </>
                  ) : (
                    <span className="badge">未購入</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
