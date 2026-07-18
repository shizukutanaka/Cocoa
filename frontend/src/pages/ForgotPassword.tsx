import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import * as authService from "../services/authService";
import { apiErrorMessage } from "../services/apiClient";
import { usePageTitle } from "../hooks/usePageTitle";

export function ForgotPassword() {
  usePageTitle("パスワードの再設定");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  // Only present in local dev when the server sets COCOA_EXPOSE_RESET_TOKEN.
  const [devToken, setDevToken] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await authService.requestPasswordReset(email);
      setSent(true);
      setDevToken(res.dev_token ?? null);
    } catch (err) {
      setError(apiErrorMessage(err, "リクエストに失敗しました"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <h1>パスワードの再設定</h1>
      {sent ? (
        <>
          <p className="subhead">
            入力されたメールアドレスが登録されている場合、再設定用のリンクを送信しました。メールをご確認ください。
          </p>
          {devToken && (
            <div className="card card-pad" style={{ fontSize: 13, marginBottom: 12 }}>
              <div style={{ color: "var(--muted)" }}>開発用トークン（本番では表示されません）:</div>
              <code style={{ wordBreak: "break-all" }}>{devToken}</code>
              <div style={{ marginTop: 8 }}>
                <Link to={`/reset-password?token=${encodeURIComponent(devToken)}`}>
                  このトークンで再設定に進む
                </Link>
              </div>
            </div>
          )}
          <p style={{ fontSize: 13 }}>
            <Link to="/reset-password">再設定コードをお持ちの方はこちら</Link>
          </p>
        </>
      ) : (
        <>
          <p className="subhead">登録済みのメールアドレスを入力してください。再設定用のコードをお送りします。</p>
          {error && <div className="form-error-banner">{error}</div>}
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="reset-email">メールアドレス</label>
              <input
                id="reset-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoFocus
                required
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={busy} style={{ width: "100%" }}>
              {busy ? "送信中..." : "再設定リンクを送る"}
            </button>
          </form>
          <p style={{ marginTop: 12, fontSize: 13 }}>
            <Link to="/login">ログインに戻る</Link>
          </p>
        </>
      )}
    </div>
  );
}
