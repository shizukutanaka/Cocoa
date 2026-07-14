import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../../hooks/useToast";
import * as authService from "../../services/authService";
import * as membershipService from "../../services/membershipService";
import { apiErrorMessage } from "../../services/apiClient";

const TIER_LABEL_JA: Record<string, string> = {
  bronze: "ブロンズ",
  silver: "シルバー",
  gold: "ゴールド",
  diamond: "ダイヤモンド",
};

function MembershipCard() {
  const { data: membership } = useQuery({
    queryKey: ["my-membership"],
    queryFn: membershipService.getMyMembership,
  });

  if (!membership) return null;

  return (
    <div className="card card-pad" style={{ maxWidth: 480, marginBottom: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 13, color: "var(--muted)" }}>会員ランク</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>
            {TIER_LABEL_JA[membership.tier] ?? membership.tier_label}
          </div>
        </div>
        {membership.fee_discount_percent > 0 && (
          <span className="badge badge-success">手数料 {membership.fee_discount_percent}% 割引</span>
        )}
      </div>
      <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 8 }}>
        累計購入 {membership.lifetime_credits.toLocaleString()} cr
        {membership.credits_to_next_tier != null && (
          <> · 次のランクまであと {membership.credits_to_next_tier.toLocaleString()} cr</>
        )}
      </div>
    </div>
  );
}

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
      <MembershipCard />
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
