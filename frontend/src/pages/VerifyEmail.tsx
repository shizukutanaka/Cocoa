import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import * as authService from "../services/authService";
import { apiErrorMessage } from "../services/apiClient";
import { usePageTitle } from "../hooks/usePageTitle";
import { useAuth } from "../hooks/useAuth";

/**
 * Landing page for the link in the verification email
 * (/verify-email?token=...). No login is required -- the token itself is the
 * credential, so the link works even on a device where the user isn't
 * signed in.
 */
export function VerifyEmail() {
  usePageTitle("メールアドレスの確認");
  const [params] = useSearchParams();
  const { refresh, user } = useAuth();
  // Pre-fill from the email link but keep it editable, mirroring /reset-password.
  const [token, setToken] = useState(params.get("token") ?? "");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await authService.verifyEmail(token.trim());
      setDone(true);
      // If the user happens to be signed in, refresh so is_email_verified
      // propagates to the UI (e.g. the Security page banner).
      if (user) await refresh();
    } catch (err) {
      setError(apiErrorMessage(err, "確認に失敗しました。トークンが無効または期限切れの可能性があります。"));
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="auth-shell">
        <h1>メールアドレスを確認しました</h1>
        <p className="subhead">ありがとうございます。アカウントのメールアドレスが確認済みになりました。</p>
        <p style={{ fontSize: 13 }}>
          {user ? <Link to="/me">マイページへ</Link> : <Link to="/login">ログインへ</Link>}
        </p>
      </div>
    );
  }

  return (
    <div className="auth-shell">
      <h1>メールアドレスの確認</h1>
      <p className="subhead">メールに記載された確認コードを入力してください。</p>
      {error && <div className="form-error-banner">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="verify-token">確認コード</label>
          <input id="verify-token" value={token} onChange={(e) => setToken(e.target.value)} required />
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy} style={{ width: "100%" }}>
          {busy ? "確認中..." : "メールアドレスを確認する"}
        </button>
      </form>
    </div>
  );
}
