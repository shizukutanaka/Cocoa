import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import * as authService from "../services/authService";
import { apiErrorMessage } from "../services/apiClient";
import { useToast } from "../hooks/useToast";
import { usePageTitle } from "../hooks/usePageTitle";

export function ResetPassword() {
  usePageTitle("新しいパスワードの設定");
  const [params] = useSearchParams();
  const { show } = useToast();
  const navigate = useNavigate();
  // Pre-fill the token from the email link (/reset-password?token=...) but keep
  // it editable so a manually-copied code also works.
  const [token, setToken] = useState(params.get("token") ?? "");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("パスワードが一致しません");
      return;
    }
    setBusy(true);
    try {
      await authService.confirmPasswordReset(token.trim(), password);
      show("パスワードを再設定しました。新しいパスワードでログインしてください。");
      navigate("/login", { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err, "再設定に失敗しました。コードが無効または期限切れの可能性があります。"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <h1>新しいパスワードの設定</h1>
      <p className="subhead">メールに記載された再設定コードと、新しいパスワードを入力してください。</p>
      {error && <div className="form-error-banner">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="reset-token">再設定コード</label>
          <input id="reset-token" value={token} onChange={(e) => setToken(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="reset-new-password">新しいパスワード</label>
          <input
            id="reset-new-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
          <span style={{ fontSize: 12, color: "var(--faint)" }}>8文字以上、数字と文字を含めてください</span>
        </div>
        <div className="field">
          <label htmlFor="reset-confirm-password">新しいパスワード（確認）</label>
          <input
            id="reset-confirm-password"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy} style={{ width: "100%" }}>
          {busy ? "設定中..." : "パスワードを再設定する"}
        </button>
      </form>
      <p style={{ marginTop: 12, fontSize: 13 }}>
        <Link to="/login">ログインに戻る</Link>
      </p>
    </div>
  );
}
