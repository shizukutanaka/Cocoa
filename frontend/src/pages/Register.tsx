import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import * as authService from "../services/authService";
import { apiErrorMessage } from "../services/apiClient";
import { useAuth } from "../hooks/useAuth";

export function Register() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const { refresh } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await authService.register(username, email, password);
      await authService.login(username, password);
      await refresh();
      navigate("/", { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err, "登録に失敗しました"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <h1>新規登録</h1>
      <p className="subhead">登録すると50クレジットが付与されます。</p>
      {error && <div className="form-error-banner">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="username">ユーザー名</label>
          <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
        </div>
        <div className="field">
          <label htmlFor="email">メールアドレス</label>
          <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="password">パスワード</label>
          <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
          <span style={{ fontSize: 12, color: "var(--faint)" }}>8文字以上、数字と文字を含めてください</span>
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy} style={{ width: "100%" }}>
          {busy ? "登録中..." : "登録する"}
        </button>
      </form>
    </div>
  );
}
