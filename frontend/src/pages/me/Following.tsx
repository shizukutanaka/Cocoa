import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import * as userService from "../../services/userService";
import { CenterSpinner } from "../../components/Spinner";
import { useToast } from "../../hooks/useToast";
import { usePageTitle } from "../../hooks/usePageTitle";
import { apiErrorMessage } from "../../services/apiClient";

export function Following() {
  usePageTitle("フォロー中");
  const { show } = useToast();
  const queryClient = useQueryClient();

  const { data: following, isLoading } = useQuery({
    queryKey: ["my-following"],
    queryFn: userService.getMyFollowing,
  });

  async function handleUnfollow(creatorId: string) {
    try {
      await userService.unfollowCreator(creatorId);
      queryClient.invalidateQueries({ queryKey: ["my-following"] });
    } catch (err) {
      show(apiErrorMessage(err, "フォロー解除に失敗しました"), "error");
    }
  }

  if (isLoading) return <CenterSpinner />;

  return (
    <div>
      <h1>フォロー中のクリエイター</h1>
      <p style={{ color: "var(--muted)", fontSize: 14 }}>
        フォロー中のクリエイターが新しいアバターを公開すると通知が届きます。
      </p>
      {!following || following.length === 0 ? (
        <div className="empty-state">
          まだ誰もフォローしていません。気になるクリエイターのページからフォローできます。
        </div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {following.map((p) => (
              <div key={p.user_id} className="row-item">
                <div>
                  <Link to={`/users/${p.user_id}`} style={{ fontWeight: 600 }}>
                    {p.display_name}
                  </Link>
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>
                    @{p.username}
                    {p.is_creator_verified && " · ✓ 認証済み"}
                  </div>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={() => handleUnfollow(p.user_id)}>
                  フォロー解除
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
