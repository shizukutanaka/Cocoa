import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import * as userService from "../services/userService";
import { CenterSpinner } from "../components/Spinner";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { usePageTitle } from "../hooks/usePageTitle";
import { apiErrorMessage } from "../services/apiClient";

export function Creator() {
  const { userId } = useParams<{ userId: string }>();
  const { user } = useAuth();
  const { show } = useToast();
  const queryClient = useQueryClient();

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
          {profile.avatar_url ? (
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
          {profile.website_url && (
            <a href={profile.website_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 13 }}>
              {profile.website_url}
            </a>
          )}
        </div>
        {user && !isSelf && (
          <button
            className={isFollowing ? "btn btn-secondary" : "btn btn-primary"}
            onClick={handleToggleFollow}
            aria-pressed={isFollowing}
          >
            {isFollowing ? "フォロー中" : "フォローする"}
          </button>
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
