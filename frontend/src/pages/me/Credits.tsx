import { useQuery } from "@tanstack/react-query";
import { getBalance, getHistory } from "../../services/creditsService";
import { CenterSpinner } from "../../components/Spinner";

export function Credits() {
  const { data: balance, isLoading: loadingBalance } = useQuery({ queryKey: ["credits-balance"], queryFn: getBalance });
  const { data: history, isLoading: loadingHistory } = useQuery({ queryKey: ["credits-history"], queryFn: () => getHistory(50, 0) });

  return (
    <div>
      <h1>クレジット</h1>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="stat-value">{loadingBalance ? "..." : balance?.toLocaleString()}</div>
          <div className="stat-label">現在の残高</div>
        </div>
      </div>

      <h2 style={{ fontSize: 16, marginTop: 24 }}>取引履歴</h2>
      {loadingHistory ? (
        <CenterSpinner />
      ) : !history || history.items.length === 0 ? (
        <div className="empty-state">取引履歴がありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {history.items.map((entry, i) => (
              <div key={i} className="row-item">
                <div>
                  <div style={{ fontWeight: 600 }}>{entry.kind}</div>
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>{new Date(entry.ts).toLocaleString("ja-JP")}</div>
                </div>
                <span
                  className="listing-price"
                  style={{ color: entry.amount >= 0 ? "var(--success)" : "var(--danger)" }}
                >
                  {entry.amount >= 0 ? "+" : ""}
                  {entry.amount.toLocaleString()} cr
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
