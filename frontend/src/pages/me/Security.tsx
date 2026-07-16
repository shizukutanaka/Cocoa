import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import * as authService from "../../services/authService";
import { apiErrorMessage } from "../../services/apiClient";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../../hooks/useToast";
import { CenterSpinner } from "../../components/Spinner";
import type { ApiKey, TwoFactorSetupData } from "../../types/api";

export function Security() {
  const { user, logout } = useAuth();
  const { show } = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data: status, isLoading } = useQuery({
    queryKey: ["2fa-status"],
    queryFn: authService.getTwoFactorStatus,
  });

  if (isLoading) return <CenterSpinner />;

  return (
    <div>
      <h1>セキュリティ</h1>
      <TwoFactorSection enabled={!!status?.is_enabled} username={user!.username} onChanged={() => queryClient.invalidateQueries({ queryKey: ["2fa-status"] })} />
      <ChangePasswordSection />
      <ApiKeysSection />
      <DangerZoneSection
        onDeleted={async () => {
          await logout();
          navigate("/login");
          show("アカウントを削除しました");
        }}
      />
    </div>
  );
}

function TwoFactorSection({ enabled, username, onChanged }: { enabled: boolean; username: string; onChanged: () => void }) {
  const { show } = useToast();
  const [setupData, setSetupData] = useState<TwoFactorSetupData | null>(null);
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleStartSetup() {
    setBusy(true);
    try {
      const result = await authService.setupTwoFactor(username);
      setSetupData(result.setup_data);
    } catch (err) {
      show(apiErrorMessage(err, "セットアップの開始に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleEnable(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await authService.enableTwoFactor(username, token);
      show("2要素認証を有効にしました");
      setSetupData(null);
      setToken("");
      onChanged();
    } catch (err) {
      show(apiErrorMessage(err, "確認コードが正しくありません"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleDisable(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await authService.disableTwoFactor(password);
      show("2要素認証を無効にしました");
      setPassword("");
      onChanged();
    } catch (err) {
      show(apiErrorMessage(err, "無効化に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card card-pad" style={{ marginBottom: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ fontSize: 16, marginBottom: 2 }}>2要素認証（2FA）</h2>
          <p style={{ color: "var(--muted)", fontSize: 13, margin: 0 }}>
            ログイン時にパスワードに加えて認証アプリのコードを要求します。
          </p>
        </div>
        <span className={enabled ? "badge badge-success" : "badge"}>{enabled ? "有効" : "無効"}</span>
      </div>

      {enabled && !setupData && (
        <form onSubmit={handleDisable} style={{ marginTop: 16, maxWidth: 320 }}>
          <div className="field">
            <label htmlFor="disable-password">無効化するにはパスワードを入力してください</label>
            <input id="disable-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <button type="submit" className="btn btn-danger" disabled={busy}>
            2要素認証を無効化
          </button>
        </form>
      )}

      {!enabled && !setupData && (
        <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={handleStartSetup} disabled={busy}>
          2要素認証を設定する
        </button>
      )}

      {!enabled && setupData && (
        <div style={{ marginTop: 16 }}>
          <p>認証アプリ（Google Authenticator など）でQRコードを読み取ってください。</p>
          {setupData.qr_code_image && (
            <div className="qr-box">
              <img src={setupData.qr_code_image} alt="2FA QRコード" />
            </div>
          )}
          <p style={{ fontSize: 13, color: "var(--muted)" }}>
            読み取れない場合は手動でこのキーを入力してください: <code>{setupData.secret}</code>
          </p>

          <p style={{ marginTop: 12 }}>バックアップコード（紛失時の復旧用、各1回のみ使用可）:</p>
          <div className="backup-codes">
            {setupData.backup_codes.map((c) => (
              <span key={c}>{c}</span>
            ))}
          </div>

          <form onSubmit={handleEnable} style={{ maxWidth: 260, marginTop: 12 }}>
            <div className="field">
              <label htmlFor="enable-token">認証アプリの6桁コードを入力して有効化</label>
              <input id="enable-token" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="one-time-code" required />
            </div>
            <button type="submit" className="btn btn-primary" disabled={busy}>
              有効化
            </button>
          </form>
        </div>
      )}
    </section>
  );
}

function ChangePasswordSection() {
  const { show } = useToast();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await authService.changePassword(currentPassword, newPassword);
      show("パスワードを変更しました");
      setCurrentPassword("");
      setNewPassword("");
    } catch (err) {
      show(apiErrorMessage(err, "パスワードの変更に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card card-pad" style={{ marginBottom: 20 }}>
      <h2 style={{ fontSize: 16 }}>パスワード変更</h2>
      <form onSubmit={handleSubmit} style={{ maxWidth: 320 }}>
        <div className="field">
          <label htmlFor="current-password">現在のパスワード</label>
          <input id="current-password" type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="new-password">新しいパスワード</label>
          <input id="new-password" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={8} />
        </div>
        <button type="submit" className="btn btn-secondary" disabled={busy}>
          変更する
        </button>
      </form>
    </section>
  );
}

function ApiKeysSection() {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  // The raw key is only ever returned once, at creation -- held in local
  // state only, never persisted, never refetched.
  const [justCreated, setJustCreated] = useState<ApiKey | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["api-keys"],
    queryFn: authService.listApiKeys,
  });

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const key = await authService.createApiKey(name);
      setJustCreated(key);
      setName("");
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    } catch (err) {
      show(apiErrorMessage(err, "APIキーの作成に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke(keyId: string) {
    if (!window.confirm("このAPIキーを無効化しますか？（元に戻せません）")) return;
    try {
      await authService.revokeApiKey(keyId);
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    } catch (err) {
      show(apiErrorMessage(err, "無効化に失敗しました"), "error");
    }
  }

  return (
    <section className="card card-pad" style={{ marginBottom: 20 }}>
      <h2 style={{ fontSize: 16 }}>APIキー</h2>
      <p style={{ color: "var(--muted)", fontSize: 13 }}>
        外部ツールからAPIを呼び出すための認証キーです。キーは作成時に一度だけ表示されます。
      </p>

      {justCreated && (
        <div className="form-error-banner" style={{ background: "var(--surface-2)", color: "var(--ink)" }}>
          <strong>{justCreated.name}</strong> を作成しました。このキーは二度と表示されません:
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 13, marginTop: 6, wordBreak: "break-all" }}>
            {justCreated.raw_key}
          </div>
          <button className="btn btn-ghost btn-sm" style={{ marginTop: 6 }} onClick={() => setJustCreated(null)}>
            閉じる
          </button>
        </div>
      )}

      <form onSubmit={handleCreate} style={{ display: "flex", gap: 8, maxWidth: 360, marginTop: 12 }}>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="キーの名前（例: CLIツール）"
          maxLength={64}
          aria-label="APIキーの名前"
        />
        <button type="submit" className="btn btn-secondary btn-sm" disabled={busy}>
          {busy ? "作成中..." : "作成"}
        </button>
      </form>

      {isLoading ? (
        <CenterSpinner />
      ) : data && data.items.length > 0 ? (
        <div className="row-list" style={{ marginTop: 12 }}>
          {data.items.map((key) => (
            <div key={key.key_id} className="row-item">
              <div>
                <strong>{key.name}</strong>
                <div style={{ fontSize: 12, color: "var(--faint)", fontFamily: "var(--font-mono)" }}>
                  {key.key_prefix}...
                </div>
                <div style={{ fontSize: 12, color: "var(--faint)" }}>
                  作成日 {new Date(key.created_at).toLocaleDateString("ja-JP")}
                  {key.last_used && ` · 最終利用 ${new Date(key.last_used).toLocaleDateString("ja-JP")}`}
                </div>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => handleRevoke(key.key_id)}>
                無効化
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ fontSize: 13, color: "var(--faint)", marginTop: 12 }}>まだAPIキーがありません。</p>
      )}
    </section>
  );
}

function DangerZoneSection({ onDeleted }: { onDeleted: () => void }) {
  const { show } = useToast();
  const [password, setPassword] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  async function handleDelete(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await authService.deleteOwnAccount(password);
      onDeleted();
    } catch (err) {
      show(apiErrorMessage(err, "アカウント削除に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card card-pad" style={{ borderColor: "var(--danger)" }}>
      <h2 style={{ fontSize: 16, color: "var(--danger)" }}>危険な操作</h2>
      <p style={{ fontSize: 13, color: "var(--muted)" }}>
        アカウントを削除すると、カート・ウィッシュリスト・コレクション・保存検索・通知・2要素認証の設定が完全に削除されます。
        クレジット残高・取引履歴・ライセンスなどの記録は保持されます。この操作は取り消せません。
      </p>
      {!confirming ? (
        <button className="btn btn-danger" onClick={() => setConfirming(true)}>
          アカウントを削除する
        </button>
      ) : (
        <form onSubmit={handleDelete} style={{ maxWidth: 320 }}>
          <div className="field">
            <label htmlFor="delete-password">確認のためパスワードを入力してください</label>
            <input id="delete-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoFocus />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" className="btn btn-danger" disabled={busy}>
              {busy ? "削除中..." : "完全に削除する"}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setConfirming(false)}>
              キャンセル
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
