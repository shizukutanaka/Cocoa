import { useState } from "react";
import * as vrchatToolsService from "../services/vrchatToolsService";
import type { VRChatParameter, VRChatStatsInput } from "../services/vrchatToolsService";
import type { VRChatBudgetResult, VRChatPerformanceResult } from "../types/api";
import { apiErrorMessage } from "../services/apiClient";
import { useToast } from "../hooks/useToast";
import { usePageTitle } from "../hooks/usePageTitle";

const PARAM_TYPES: VRChatParameter["type"][] = ["Bool", "Int", "Float", "Trigger"];

let idCounter = 0;
function newRow(): VRChatParameter & { _id: number } {
  return { _id: idCounter++, name: "", type: "Bool", synced: true };
}

export function VRChatTools() {
  usePageTitle("VRChat ツール");
  const [tab, setTab] = useState<"budget" | "performance">("budget");

  return (
    <div>
      <h1>VRChat アバターツール</h1>
      <div className="filters-bar" role="tablist" aria-label="ツールの切り替え" style={{ marginBottom: 16 }}>
        <button
          className={tab === "budget" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "budget"}
          onClick={() => setTab("budget")}
        >
          パラメータ予算
        </button>
        <button
          className={tab === "performance" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "performance"}
          onClick={() => setTab("performance")}
        >
          パフォーマンスランク
        </button>
      </div>
      {tab === "budget" ? <BudgetTool /> : <PerformanceTool />}
    </div>
  );
}

function BudgetTool() {
  const { show } = useToast();
  const [rows, setRows] = useState<Array<VRChatParameter & { _id: number }>>(() => [newRow(), newRow()]);
  const [result, setResult] = useState<VRChatBudgetResult | null>(null);
  const [busy, setBusy] = useState(false);

  function updateRow(id: number, patch: Partial<VRChatParameter>) {
    setRows((prev) => prev.map((r) => (r._id === id ? { ...r, ...patch } : r)));
  }
  function removeRow(id: number) {
    setRows((prev) => prev.filter((r) => r._id !== id));
  }

  async function handleAnalyze() {
    const params = rows
      .filter((r) => r.name.trim())
      .map(({ name, type, synced }) => ({ name: name.trim(), type, synced }));
    if (params.length === 0) {
      show("少なくとも1つのパラメータ名を入力してください", "error");
      return;
    }
    setBusy(true);
    try {
      const res = await vrchatToolsService.analyzeBudget(params);
      setResult(res);
    } catch (err) {
      show(apiErrorMessage(err, "分析に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  const usedPct = result ? Math.min(100, Math.round((result.used_bits / result.budget_bits) * 100)) : 0;

  return (
    <div>
      <p style={{ color: "var(--muted)", fontSize: 14, marginTop: 0 }}>
        アバターの同期パラメータを入力すると、VRChat の 256 ビット予算に対する使用量と最適化提案を確認できます。
      </p>

      <div className="card card-pad" style={{ maxWidth: 640, marginBottom: 20 }}>
        <div className="row-list">
          {rows.map((row) => (
            <div key={row._id} className="row-item" style={{ gap: 8 }}>
              <input
                type="text"
                value={row.name}
                onChange={(e) => updateRow(row._id, { name: e.target.value })}
                placeholder="パラメータ名"
                aria-label="パラメータ名"
                style={{ flex: 1, fontSize: 13, padding: "4px 8px" }}
              />
              <select
                value={row.type}
                onChange={(e) => updateRow(row._id, { type: e.target.value as VRChatParameter["type"] })}
                aria-label="型"
                style={{ fontSize: 13 }}
              >
                {PARAM_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13 }}>
                <input
                  type="checkbox"
                  checked={row.synced}
                  onChange={(e) => updateRow(row._id, { synced: e.target.checked })}
                />
                同期
              </label>
              <button className="btn btn-ghost btn-sm" onClick={() => removeRow(row._id)} aria-label="行を削除">
                ✕
              </button>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <button className="btn btn-secondary btn-sm" onClick={() => setRows((prev) => [...prev, newRow()])}>
            行を追加
          </button>
          <button className="btn btn-primary btn-sm" onClick={handleAnalyze} disabled={busy}>
            {busy ? "分析中..." : "分析する"}
          </button>
        </div>
      </div>

      {result && (
        <div className="card card-pad" style={{ maxWidth: 640 }}>
          <h2 style={{ fontSize: 18, marginTop: 0 }}>分析結果</h2>
          {result.over_budget ? (
            <div className="form-error-banner">
              予算超過: {result.used_bits} / {result.budget_bits} ビット使用（{result.used_bits - result.budget_bits} ビット超過）
            </div>
          ) : (
            <div style={{ fontSize: 14, marginBottom: 8 }}>
              使用量: <strong>{result.used_bits}</strong> / {result.budget_bits} ビット（残り {result.remaining_bits}）
            </div>
          )}
          <div style={{ height: 12, background: "var(--surface-2)", borderRadius: 6, overflow: "hidden", marginBottom: 12 }}>
            <div
              style={{
                width: `${usedPct}%`,
                height: "100%",
                background: result.over_budget ? "var(--warning)" : "var(--accent)",
              }}
            />
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, fontSize: 13, marginBottom: 12 }}>
            <span>同期パラメータ数: {result.synced_count}</span>
            {Object.entries(result.per_type_bits).map(([type, bits]) => (
              <span key={type} style={{ color: "var(--muted)" }}>
                {type}: {result.breakdown[type] ?? 0}個 / {bits}ビット
              </span>
            ))}
          </div>

          {result.suggestions.length > 0 && (
            <div>
              <h3 style={{ fontSize: 14 }}>最適化の提案</h3>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                {result.suggestions.map((s, i) => (
                  <li key={i} style={{ marginBottom: 4 }}>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {result.suggestions.length === 0 && !result.over_budget && (
            <p style={{ fontSize: 13, color: "var(--success)" }}>予算内に収まっています。最適化の必要はありません。</p>
          )}
        </div>
      )}
    </div>
  );
}

const STAT_FIELDS: Array<{ key: keyof Omit<VRChatStatsInput, "platform">; label: string }> = [
  { key: "polygons", label: "ポリゴン数" },
  { key: "materials", label: "マテリアル数" },
  { key: "bones", label: "ボーン数" },
  { key: "physbones_components", label: "PhysBones コンポーネント数" },
  { key: "physbones_colliders", label: "PhysBones コライダー数" },
  { key: "texture_memory_mb", label: "テクスチャメモリ（MB）" },
];

const RANK_LABEL: Record<string, { label: string; color: string }> = {
  excellent: { label: "Excellent", color: "var(--success)" },
  good: { label: "Good", color: "var(--success)" },
  medium: { label: "Medium", color: "var(--warning)" },
  poor: { label: "Poor", color: "var(--warning)" },
  very_poor: { label: "Very Poor", color: "var(--danger, #d64545)" },
};

function PerformanceTool() {
  const { show } = useToast();
  const [stats, setStats] = useState<VRChatStatsInput>({
    polygons: 0,
    materials: 0,
    bones: 0,
    physbones_components: 0,
    physbones_colliders: 0,
    texture_memory_mb: 0,
    platform: "PC",
  });
  const [result, setResult] = useState<VRChatPerformanceResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleAnalyze() {
    setBusy(true);
    try {
      const res = await vrchatToolsService.analyzePerformance(stats);
      setResult(res);
    } catch (err) {
      show(apiErrorMessage(err, "分析に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  const rank = result ? RANK_LABEL[result.rank] ?? { label: result.rank, color: "var(--muted)" } : null;

  return (
    <div>
      <p style={{ color: "var(--muted)", fontSize: 14, marginTop: 0 }}>
        アバターのスペックを入力すると、VRChat のパフォーマンスランク（Excellent〜Very Poor）と改善提案を確認できます。
      </p>

      <div className="card card-pad" style={{ maxWidth: 640, marginBottom: 20 }}>
        <div className="field">
          <label htmlFor="perf-platform">プラットフォーム</label>
          <select
            id="perf-platform"
            value={stats.platform}
            onChange={(e) => setStats((s) => ({ ...s, platform: e.target.value as VRChatStatsInput["platform"] }))}
          >
            <option value="PC">PC</option>
            <option value="Quest">Quest</option>
          </select>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {STAT_FIELDS.map((f) => (
            <div className="field" key={f.key}>
              <label htmlFor={`perf-${f.key}`}>{f.label}</label>
              <input
                id={`perf-${f.key}`}
                type="number"
                min={0}
                value={stats[f.key]}
                onChange={(e) => setStats((s) => ({ ...s, [f.key]: Number(e.target.value) }))}
              />
            </div>
          ))}
        </div>
        <button className="btn btn-primary btn-sm" onClick={handleAnalyze} disabled={busy} style={{ marginTop: 8 }}>
          {busy ? "分析中..." : "分析する"}
        </button>
      </div>

      {result && rank && (
        <div className="card card-pad" style={{ maxWidth: 640 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
            <span style={{ fontSize: 22, fontWeight: 700, color: rank.color }}>{rank.label}</span>
            <span style={{ fontSize: 13, color: "var(--muted)" }}>
              スコア {result.score} · {result.platform}
            </span>
          </div>

          {result.issues.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <h3 style={{ fontSize: 14 }}>検出された問題</h3>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                {result.issues.map((issue, i) => (
                  <li key={i}>{issue.message}</li>
                ))}
              </ul>
            </div>
          )}

          {result.suggestions.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <h3 style={{ fontSize: 14 }}>改善の提案</h3>
              <div className="row-list">
                {result.suggestions.map((s, i) => (
                  <div key={i} className="row-item" style={{ alignItems: "flex-start" }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>
                        {s.category}
                        <span className="badge" style={{ marginLeft: 6 }}>
                          {s.severity}
                        </span>
                      </div>
                      <div style={{ fontSize: 13, color: "var(--muted)" }}>{s.suggestion}</div>
                    </div>
                    <div style={{ fontSize: 12, color: "var(--faint)", whiteSpace: "nowrap" }}>
                      {s.current_value} → {s.target_value}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.issues.length === 0 && result.suggestions.length === 0 && (
            <p style={{ fontSize: 13, color: "var(--success)", marginTop: 8 }}>問題は検出されませんでした。</p>
          )}
        </div>
      )}
    </div>
  );
}
