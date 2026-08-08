import { useState } from "react";
import { Link } from "react-router-dom";
import type { AvatarData } from "../types/api";
import { useToast } from "../hooks/useToast";

/**
 * Displays the avatar parameters a buyer received, and lets them take the data
 * away: copy the JSON to the clipboard or save it as a .json file.
 *
 * Cocoa trades avatar *parameter sets* (not model files) -- see FEATURE_AUDIT.md
 * section 1 -- so this panel is the buyer's actual delivery of the product.
 */
export function ParameterDelivery({ data, onClose }: { data: AvatarData; onClose?: () => void }) {
  const { show } = useToast();
  const [copied, setCopied] = useState(false);

  const json = JSON.stringify(data.parameters, null, 2);
  const paramCount = Object.keys(data.parameters ?? {}).length;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      show("パラメータをコピーしました");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      show("コピーに失敗しました。テキストを選択して手動でコピーしてください。", "error");
    }
  }

  function handleSave() {
    // Build the file client-side; there is no server-side file artifact.
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    // Strip characters that are unsafe in filenames across platforms.
    const safeName = (data.name || "avatar-parameters").replace(/[\\/:*?"<>|]/g, "_");
    a.download = `${safeName}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="card card-pad" id="parameter-delivery" style={{ marginTop: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
        <h3 style={{ fontSize: 16, margin: 0 }}>
          取得したパラメータ <span style={{ color: "var(--muted)", fontWeight: 400 }}>（{paramCount} 項目）</span>
        </h3>
        {onClose && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
            閉じる
          </button>
        )}
      </div>

      {data.amount_paid > 0 ? (
        <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 6 }}>
          {data.amount_paid.toLocaleString()} クレジットを支払いました。以降の再取得は無料です。
        </p>
      ) : (
        <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 6 }}>
          追加の支払いはありません。購入済みの作品は何度でも無料で取得できます。
        </p>
      )}

      <div style={{ display: "flex", gap: 8, margin: "12px 0", flexWrap: "wrap" }}>
        <button type="button" id="param-copy" className="btn btn-primary btn-sm" onClick={handleCopy}>
          {copied ? "コピーしました" : "JSONをコピー"}
        </button>
        <button type="button" id="param-save" className="btn btn-secondary btn-sm" onClick={handleSave}>
          .json ファイルとして保存
        </button>
        <Link to="/tools/vrchat" className="btn btn-secondary btn-sm">
          VRChatツールで確認する
        </Link>
      </div>

      {paramCount === 0 ? (
        <div className="empty-state" style={{ padding: 24 }}>
          この作品にはパラメータが登録されていません。
        </div>
      ) : (
        <pre
          id="param-json"
          style={{
            background: "var(--surface-2)",
            padding: 12,
            borderRadius: "var(--radius-sm)",
            maxHeight: 320,
            overflow: "auto",
            fontSize: 12,
            margin: 0,
          }}
        >
          {json}
        </pre>
      )}
    </div>
  );
}
