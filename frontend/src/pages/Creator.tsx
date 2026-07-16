import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { isSafeHttpUrl } from "../utils/url";
import * as userService from "../services/userService";
import * as tipService from "../services/tipService";
import * as commissionService from "../services/commissionService";
import { CenterSpinner } from "../components/Spinner";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { usePageTitle } from "../hooks/usePageTitle";
import { apiErrorMessage } from "../services/apiClient";

export function Creator() {
  const { userId } = useParams<{ userId: string }>();
  const { user } = useAuth();
  const { show } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showTipForm, setShowTipForm] = useState(false);
  const [tipAmount, setTipAmount] = useState(10);
  const [tipMessage, setTipMessage] = useState("");
  const [sendingTip, setSendingTip] = useState(false);
  const [showCommissionForm, setShowCommissionForm] = useState(false);
  const [commissionTitle, setCommissionTitle] = useState("");
  const [commissionDescription, setCommissionDescription] = useState("");
  const [commissionBudget, setCommissionBudget] = useState(0);
  const [sendingCommission, setSendingCommission] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["storefront", userId],
    queryFn: () => userService.getStorefront(userId!),
    enabled: !!userId,
  });

  // Whether the logged-in user already follows this creator: derived from the
  // full following list (there is no per-creator check endpoint).
  const { data: following } = useQuery({
    queryKey: ["my-following"],
    queryFn: userService.getMyFollowing,
    enabled: !!user,
  });

  usePageTitle(data?.profile.display_name);

  const isSelf = user?.user_id === userId;
  const isFollowing = !!following?.some((p) => p.user_id === userId);

  async function handleToggleFollow() {
    if (!userId) return;
    try {
      if (isFollowing) {
        await userService.unfollowCreator(userId);
        show("フォローを解除しました");
      } else {
        await userService.followCreator(userId);
        show("フォローしました");
      }
      queryClient.invalidateQueries({ queryKey: ["my-following"] });
      queryClient.invalidateQueries({ queryKey: ["storefront", userId] });
    } catch (err) {
      show(apiErrorMessage(err, "フォロー状態の更新に失敗しました"), "error");
    }
  }

  async function handleSendTip() {
    if (!userId || tipAmount <= 0) return;
    setSendingTip(true);
    try {
      await tipService.sendTip(userId, tipAmount, tipMessage);
      show(`${tipAmount} クレジットのチップを送りました`);
      setShowTipForm(false);
      setTipMessage("");
    } catch (err) {
      show(apiErrorMessage(err, "チップの送信に失敗しました"), "error");
    } finally {
      setSendingTip(false);
    }
  }

  async function handleSendCommission() {
    if (!userId || !commissionTitle.trim() || !commissionDescription.trim()) return;
    setSendingCommission(true);
    try {
      await commissionService.createCommission(userId, commissionTitle, commissionDescription, commissionBudget);
      show("コミッションを依頼しました");
      setShowCommissionForm(false);
      setCommissionTitle("");
      setCommissionDescription("");
      setCommissionBudget(0);
      navigate("/me/commissions");
    } catch (err) {
      show(apiErrorMessage(err, "コミッションの依頼に失敗しました"), "error");
    } finally {
      setSendingCommission(false);
    }
  }

  if (isLoading) return <CenterSpinner />;
  if (isError || !data) return <div className="empty-state">クリエイターが見つかりませんでした。</div>;

  const { profile, listings, analytics } = data;

  return (
    <div>
      <div className="card card-pad" style={{ display: "flex", gap: 20, alignItems: "flex-start", marginBottom: 24 }}>
        <div
          className="listing-thumb"
          style={{ width: 88, height: 88, borderRadius: "50%", flexShrink: 0, overflow: "hidden" }}
        >
          {profile.avatar_url && isSafeHttpUrl(profile.avatar_url) ? (
            <img src={profile.avatar_url} alt="" style={{ borderRadius: "50%" }} />
          ) : (
            profile.display_name.slice(0, 2)
          )}
        </div>
        <div style={{ flex: 1 }}>
          <h1 style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 4 }}>
            {profile.display_name}
            {profile.is_creator_verified && (
              <span className="badge badge-success" title="認証済みクリエイター">
                ✓ 認証済み
              </span>
            )}
          </h1>
          <p style={{ color: "var(--muted)", fontSize: 14, margin: 0 }}>
            @{profile.username} · フォロワー {profile.followers_count ?? 0} 人 ·{" "}
            {new Date(profile.created_at).toLocaleDateString("ja-JP")} から活動
          </p>
          {profile.bio && <p style={{ marginTop: 8 }}>{profile.bio}</p>}
          {profile.website_url && isSafeHttpUrl(profile.website_url) && (
            <a href={profile.website_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 13 }}>
              {profile.website_url}
            </a>
          )}
        </div>
        {user && !isSelf && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                className={isFollowing ? "btn btn-secondary" : "btn btn-primary"}
                onClick={handleToggleFollow}
                aria-pressed={isFollowing}
              >
                {isFollowing ? "フォロー中" : "フォローする"}
              </button>
              <button className="btn btn-secondary" onClick={() => setShowTipForm((v) => !v)}>
                チップを送る
              </button>
              <button className="btn btn-secondary" onClick={() => setShowCommissionForm((v) => !v)}>
                コミッションを依頼する
              </button>
            </div>
            {showTipForm && (
              <div className="card card-pad" style={{ width: 260 }}>
                <div className="field">
                  <label htmlFor="tip-amount">金額（クレジット）</label>
                  <input
                    id="tip-amount"
                    type="number"
                    min={1}
                    max={10000}
                    value={tipAmount}
                    onChange={(e) => setTipAmount(Number(e.target.value))}
                  />
                </div>
                <div className="field">
                  <label htmlFor="tip-message">メッセージ（任意）</label>
                  <input
                    id="tip-message"
                    value={tipMessage}
                    onChange={(e) => setTipMessage(e.target.value)}
                    maxLength={300}
                    placeholder="応援しています！"
                  />
                </div>
                <button id="tip-submit" className="btn btn-primary btn-sm" onClick={handleSendTip} disabled={sendingTip}>
                  {sendingTip ? "送信中..." : "送る"}
                </button>
              </div>
            )}
            {showCommissionForm && (
              <div className="card card-pad" style={{ width: 300 }}>
                <div className="field">
                  <label htmlFor="commission-title">タイトル</label>
                  <input
                    id="commission-title"
                    value={commissionTitle}
                    onChange={(e) => setCommissionTitle(e.target.value)}
                    maxLength={100}
                    placeholder="オリジナルアバターの制作"
                  />
                </div>
                <div className="field">
                  <label htmlFor="commission-description">依頼内容</label>
                  <textarea
                    id="commission-description"
                    value={commissionDescription}
                    onChange={(e) => setCommissionDescription(e.target.value)}
                    rows={3}
                    maxLength={2000}
                  />
                </div>
                <div className="field">
                  <label htmlFor="commission-budget">予算（クレジット、任意）</label>
                  <input
                    id="commission-budget"
                    type="number"
                    min={0}
                    value={commissionBudget}
                    onChange={(e) => setCommissionBudget(Number(e.target.value))}
                  />
                  <span style={{ fontSize: 12, color: "var(--faint)" }}>
                    参考情報です。実際の支払いはマーケットプレイス経由で別途行います。
                  </span>
                </div>
                <button
                  id="commission-submit"
                  className="btn btn-primary btn-sm"
                  onClick={handleSendCommission}
                  disabled={sendingCommission}
                >
                  {sendingCommission ? "送信中..." : "依頼する"}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {analytics && (
        <div className="stat-row" style={{ marginBottom: 24 }}>
          <div className="stat-tile">
            <div className="stat-value">{listings.total}</div>
            <div className="stat-label">公開リスティング</div>
          </div>
          <div className="stat-tile">
            <div className="stat-value">{(analytics.total_downloads ?? 0).toLocaleString()}</div>
            <div className="stat-label">総ダウンロード数</div>
          </div>
          <div className="stat-tile">
            <div className="stat-value">{analytics.total_reviews ?? 0}</div>
            <div className="stat-label">レビュー数</div>
          </div>
        </div>
      )}

      <h2 style={{ fontSize: 18 }}>リスティング</h2>
      {listings.items.length === 0 ? (
        <div className="empty-state">公開中のリスティングはありません。</div>
      ) : (
        <div className="listing-grid">
          {listings.items.map((listing) => (
            <Link key={listing.listing_id} to={`/listings/${listing.listing_id}`} className="card listing-card">
              <div className="listing-thumb">
                {listing.thumbnail_url ? <img src={listing.thumbnail_url} alt="" loading="lazy" /> : "No Image"}
              </div>
              <div className="listing-body">
                <div className="listing-name">{listing.name}</div>
                <div className="listing-meta">
                  <span>
                    {listing.rating_count > 0 ? `★ ${listing.average_rating.toFixed(1)}` : "評価なし"}
                  </span>
                  <span className={listing.is_free ? "listing-price is-free" : "listing-price"}>
                    {listing.is_free ? "無料" : `${listing.price_credits.toLocaleString()} cr`}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
