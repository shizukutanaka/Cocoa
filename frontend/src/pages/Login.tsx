import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import * as authService from "../services/authService";
import { apiErrorMessage } from "../services/apiClient";
import { useAuth } from "../hooks/useAuth";
import type { PendingTwoFactor } from "../types/api";

export function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState<PendingTwoFactor | null>(null);
  const [code, setCode] = useState("");
  const [isBackupCode, setIsBackupCode] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const { refresh } = useAuth();
  const navigate = useNavigate();
  const routerLocation = useLocation();
  const from = (routerLocation.state as { from?: { pathname: string } } | null)?.from?.pathname ?? "/";

  async function handlePasswordSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const result = await authService.login(username, password);
      if ("requires_2fa" in result) {
        setPending(result);
      } else {
        await refresh();
        navigate(from, { replace: true });
      }
    } catch (err) {
      setError(apiErrorMessage(err, "ログインに失敗しました"));
    } finally {
      setBusy(false);
    }
  }

  async function handleTwoFactorSubmit(e: FormEvent) {
    e.preventDefault();
    if (!pending) return;
    setError("");
    setBusy(true);
    try {
      await authService.verifyTwoFactorLogin(pending, code, isBackupCode);
      await refresh();
      navigate(from, { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err, "確認コードが正しくありません"));
    } finally {
      setBusy(false);
    }
  }

  if (pending) {
    return (
      <div className="auth-shell">
        <h1>2段階認証</h1>
        <p className="subhead">認証アプリに表示されている6桁のコード、またはバックアップコードを入力してください。</p>
        {error && <div className="form-error-banner">{error}</div>}
        <form onSubmit={handleTwoFactorSubmit}>
          <div className="field">
            <label htmlFor="code">{isBackupCode ? "バックアップコード" : "確認コード"}</label>
            <input
              id="code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              autoFocus
              autoComplete="one-time-code"
              required
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={busy} style={{ width: "100%" }}>
            {busy ? "確認中..." : "確認"}
          </button>
        </form>
        <p style={{ marginTop: 14, fontSize: 13 }}>
          <button type="button" className="btn-ghost btn" onClick={() => setIsBackupCode((v) => !v)}>
            {isBackupCode ? "認証アプリのコードを使う" : "バックアップコードを使う"}
          </button>
        </p>
      </div>
    );
  }

  return (
    <div className="auth-shell">
      <h1>ログイン</h1>
      <p className="subhead">アカウントにログインしてください。</p>
      {error && <div className="form-error-banner">{error}</div>}
      <form onSubmit={handlePasswordSubmit}>
        <div className="field">
          <label htmlFor="username">ユーザー名</label>
          <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
        </div>
        <div className="field">
          <label htmlFor="password">パスワード</label>
          <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy} style={{ width: "100%" }}>
          {busy ? "ログイン中..." : "ログイン"}
        </button>
      </form>
    </div>
  );
}
