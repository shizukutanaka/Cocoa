import { useState, type FormEvent } from "react";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../../hooks/useToast";
import * as authService from "../../services/authService";
import { apiErrorMessage } from "../../services/apiClient";

export function Profile() {
  const { user, refresh } = useAuth();
  const { show } = useToast();
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [bio, setBio] = useState(user?.bio ?? "");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await authService.updateProfile({ display_name: displayName, bio });
      await refresh();
      show("プロフィールを更新しました");
    } catch (err) {
      show(apiErrorMessage(err, "更新に失敗しました"), "error");
    } finally {
      setSaving(false);
    }
  }

  if (!user) return null;

  return (
    <div>
      <h1>プロフィール</h1>
      <div className="card card-pad" style={{ maxWidth: 480 }}>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>ユーザー名</label>
            <input value={user.username} disabled />
          </div>
          <div className="field">
            <label>メールアドレス</label>
            <input value={user.email ?? ""} disabled />
          </div>
          <div className="field">
            <label htmlFor="displayName">表示名</label>
            <input id="displayName" value={displayName} onChange={(e) => setDisplayName(e.target.value)} maxLength={64} />
          </div>
          <div className="field">
            <label htmlFor="bio">自己紹介</label>
            <textarea id="bio" value={bio} onChange={(e) => setBio(e.target.value)} rows={4} maxLength={500} />
          </div>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "保存中..." : "保存"}
          </button>
        </form>
      </div>
    </div>
  );
}
