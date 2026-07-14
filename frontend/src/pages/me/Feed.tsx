import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import * as userService from "../../services/userService";
import { CenterSpinner } from "../../components/Spinner";
import { usePageTitle } from "../../hooks/usePageTitle";

export function Feed() {
  usePageTitle("フィード");

  const { data, isLoading } = useQuery({
    queryKey: ["feed"],
    queryFn: () => userService.getFeed(30, 0),
  });

  return (
    <div>
      <h1>フィード</h1>
      <p style={{ color: "var(--muted)", fontSize: 14 }}>
        フォロー中のクリエイターが公開した新着アバターです。
      </p>

      {isLoading ? (
        <CenterSpinner />
      ) : !data || data.items.length === 0 ? (
        <div className="empty-state">
          新着はまだありません。クリエイターをフォローすると、ここに新着アバターが表示されます。
        </div>
      ) : (
        <div className="listing-grid">
          {data.items.map((listing) => (
            <Link key={listing.listing_id} to={`/listings/${listing.listing_id}`} className="card listing-card">
              <div className="listing-thumb">
                {listing.thumbnail_url ? <img src={listing.thumbnail_url} alt="" loading="lazy" /> : "No Image"}
              </div>
              <div className="listing-body">
                <div className="listing-name">{listing.name}</div>
                <div className="listing-meta">
                  <span>{listing.owner_username}</span>
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
