import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import * as marketplaceService from "../services/marketplaceService";
import { getListing, getRelated } from "../services/marketplaceService";
import { addToCart } from "../services/cartService";
import * as wishlistService from "../services/wishlistService";
import { CenterSpinner } from "../components/Spinner";
import { StarRating } from "../components/StarRating";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { usePageTitle } from "../hooks/usePageTitle";
import { apiErrorMessage } from "../services/apiClient";

export function ListingDetail() {
  const { listingId } = useParams<{ listingId: string }>();
  const { user } = useAuth();
  const { show } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [addingToCart, setAddingToCart] = useState(false);
  const [showReportForm, setShowReportForm] = useState(false);
  const [reportReason, setReportReason] = useState<string>(marketplaceService.LISTING_REPORT_REASONS[0].value);
  const [reportDetails, setReportDetails] = useState("");
  const [reportingListing, setReportingListing] = useState(false);
  const [cloning, setCloning] = useState(false);

  const { data: listing, isLoading, isError } = useQuery({
    queryKey: ["listing", listingId],
    queryFn: () => getListing(listingId!),
    enabled: !!listingId,
  });

  const { data: inWishlist } = useQuery({
    queryKey: ["wishlist-check", listingId],
    queryFn: () => wishlistService.checkWishlist(listingId!),
    enabled: !!listingId && !!user,
  });

  const { data: priceHistory } = useQuery({
    queryKey: ["price-history", listingId],
    queryFn: () => marketplaceService.getPriceHistory(listingId!),
    enabled: !!listingId,
  });

  const { data: related } = useQuery({
    queryKey: ["related", listingId],
    queryFn: () => getRelated(listingId!),
    enabled: !!listingId,
  });

  usePageTitle(listing?.name);

  async function handleAddToCart() {
    if (!listing) return;
    setAddingToCart(true);
    try {
      await addToCart(listing.listing_id);
      queryClient.invalidateQueries({ queryKey: ["cart"] });
      show("カートに追加しました");
    } catch (err) {
      show(apiErrorMessage(err, "カートへの追加に失敗しました"), "error");
    } finally {
      setAddingToCart(false);
    }
  }

  async function handleToggleWishlist() {
    if (!listing) return;
    try {
      if (inWishlist) {
        await wishlistService.removeFromWishlist(listing.listing_id);
        show("ウィッシュリストから削除しました");
      } else {
        await wishlistService.addToWishlist(listing.listing_id);
        show("ウィッシュリストに追加しました");
      }
      queryClient.invalidateQueries({ queryKey: ["wishlist-check", listingId] });
    } catch (err) {
      show(apiErrorMessage(err, "ウィッシュリストの更新に失敗しました"), "error");
    }
  }

  async function handleClone() {
    if (!listing) return;
    setCloning(true);
    try {
      const cloned = await marketplaceService.cloneListing(listing.listing_id);
      show("クローンして公開しました");
      navigate(`/listings/${cloned.listing_id}`);
    } catch (err) {
      show(apiErrorMessage(err, "クローンに失敗しました"), "error");
    } finally {
      setCloning(false);
    }
  }

  async function handleReportListing() {
    if (!listing) return;
    setReportingListing(true);
    try {
      await marketplaceService.reportListing(listing.listing_id, reportReason, reportDetails);
      show("通報を受け付けました");
      setShowReportForm(false);
      setReportDetails("");
    } catch (err) {
      show(apiErrorMessage(err, "通報に失敗しました"), "error");
    } finally {
      setReportingListing(false);
    }
  }

  if (isLoading) return <CenterSpinner />;
  if (isError || !listing) return <div className="empty-state">リスティングが見つかりませんでした。</div>;

  const isOwnListing = user?.user_id === listing.owner_id;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 }}>
      <div className="card listing-thumb" style={{ aspectRatio: "1", borderRadius: "var(--radius)" }}>
        {listing.thumbnail_url ? <img src={listing.thumbnail_url} alt="" loading="lazy" /> : "No Image"}
      </div>

      <div>
        <h1 style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          {listing.name}
          {listing.is_ai_generated && (
            <span className="badge badge-ai" title="AI生成コンテンツを含む">
              AI生成
            </span>
          )}
        </h1>
        <p style={{ color: "var(--muted)" }}>
          by <Link to={`/users/${listing.owner_id}`}>{listing.owner_username}</Link> · {listing.platform || "汎用"}
        </p>

        <div style={{ display: "flex", gap: 8, margin: "12px 0" }}>
          {listing.tags.map((tag) => (
            <span key={tag} className="badge">
              {tag}
            </span>
          ))}
        </div>

        <p>{listing.description}</p>

        {listing.parameter_count > 0 && (
          <div style={{ margin: "12px 0" }}>
            <div style={{ fontSize: 13, color: "var(--muted)" }}>
              パラメータ {listing.parameter_count} 件（購入するとすべての値が利用可能になります）
            </div>
            {listing.parameter_keys_preview.length > 0 && (
              <div className="param-chips">
                {listing.parameter_keys_preview.map((k) => (
                  <span key={k} className="param-chip">
                    {k}
                  </span>
                ))}
                {listing.parameter_count > listing.parameter_keys_preview.length && (
                  <span className="param-chip">
                    +{listing.parameter_count - listing.parameter_keys_preview.length}
                  </span>
                )}
              </div>
            )}
          </div>
        )}

        {priceHistory && priceHistory.length > 1 && (
          <details style={{ margin: "8px 0" }}>
            <summary style={{ cursor: "pointer", fontSize: 13, color: "var(--muted)" }}>価格の変更履歴</summary>
            <div style={{ marginTop: 6, display: "grid", gap: 4 }}>
              {priceHistory
                .slice()
                .reverse()
                .map((entry, i) => (
                  <div key={i} style={{ fontSize: 13, display: "flex", gap: 8 }}>
                    <span style={{ color: "var(--faint)" }}>
                      {new Date(entry.changed_at).toLocaleDateString("ja-JP")}
                    </span>
                    <span>{entry.is_free ? "無料" : `${entry.price_credits.toLocaleString()} cr`}</span>
                  </div>
                ))}
            </div>
          </details>
        )}

        <div className="stat-row">
          <div className="stat-tile">
            <div className="stat-value">{listing.is_free ? "無料" : `${listing.price_credits.toLocaleString()} cr`}</div>
            <div className="stat-label">価格</div>
          </div>
          <div className="stat-tile">
            <div className="stat-value">
              {listing.rating_count > 0 ? listing.average_rating.toFixed(1) : "-"}
            </div>
            <div className="stat-label">評価（{listing.rating_count}件）</div>
          </div>
          <div className="stat-tile">
            <div className="stat-value">{listing.download_count.toLocaleString()}</div>
            <div className="stat-label">ダウンロード数</div>
          </div>
        </div>

        {listing.is_sold_out && <div className="form-error-banner">在庫切れです</div>}

        {!isOwnListing && (
          <div style={{ display: "flex", gap: 8 }}>
            {!listing.is_sold_out && (
              <button className="btn btn-primary" onClick={handleAddToCart} disabled={addingToCart}>
                {addingToCart ? "追加中..." : "カートに追加"}
              </button>
            )}
            {user && (
              <button
                className="btn btn-secondary"
                onClick={handleToggleWishlist}
                aria-pressed={!!inWishlist}
                aria-label={inWishlist ? "ウィッシュリストから削除" : "ウィッシュリストに追加"}
              >
                {inWishlist ? "★ ウィッシュリスト済み" : "☆ ウィッシュリストに追加"}
              </button>
            )}
          </div>
        )}
        {isOwnListing && <p style={{ color: "var(--muted)" }}>これはあなたが出品したリスティングです。</p>}

        {user && marketplaceService.CLONEABLE_LICENSES.includes(listing.license_type) && (
          <div style={{ marginTop: 10 }}>
            <button className="btn btn-secondary btn-sm" onClick={handleClone} disabled={cloning}>
              {cloning ? "クローン中..." : "クローンして自分の作品として公開"}
            </button>
            <p style={{ fontSize: 12, color: "var(--faint)", marginTop: 4 }}>
              CC BY / CC BY-SA ライセンスのため、パラメータをコピーして新しいリスティングとして公開できます。
            </p>
          </div>
        )}

        {user && !isOwnListing && (
          <div style={{ marginTop: 10 }}>
            {!showReportForm ? (
              <button className="btn btn-ghost btn-sm" onClick={() => setShowReportForm(true)}>
                このリスティングを通報する
              </button>
            ) : (
              <div className="card card-pad" style={{ maxWidth: 360 }}>
                <div className="field">
                  <label htmlFor="report-reason">理由</label>
                  <select id="report-reason" value={reportReason} onChange={(e) => setReportReason(e.target.value)}>
                    {marketplaceService.LISTING_REPORT_REASONS.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="report-details">詳細（任意）</label>
                  <textarea
                    id="report-details"
                    value={reportDetails}
                    onChange={(e) => setReportDetails(e.target.value)}
                    rows={2}
                    maxLength={1000}
                  />
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn btn-secondary btn-sm" onClick={handleReportListing} disabled={reportingListing}>
                    {reportingListing ? "送信中..." : "通報する"}
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => setShowReportForm(false)}>
                    キャンセル
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div style={{ gridColumn: "1 / -1" }}>
        <RatingDistributionSection listingId={listing.listing_id} />
      </div>

      <div style={{ gridColumn: "1 / -1" }}>
        <ReviewsSection listingId={listing.listing_id} isOwnListing={isOwnListing} isLoggedIn={!!user} />
      </div>

      <div style={{ gridColumn: "1 / -1" }}>
        <VersionHistorySection listingId={listing.listing_id} isOwnListing={isOwnListing} />
      </div>

      {related && related.length > 0 && (
        <div style={{ gridColumn: "1 / -1" }}>
          <h2 style={{ fontSize: 18 }}>関連アバター</h2>
          <div className="related-grid">
            {related.map((r) => (
              <Link key={r.listing_id} to={`/listings/${r.listing_id}`} className="card listing-card">
                <div className="listing-thumb">
                  {r.thumbnail_url ? <img src={r.thumbnail_url} alt="" loading="lazy" /> : "No Image"}
                </div>
                <div className="listing-body">
                  <div className="listing-name">{r.name}</div>
                  <div className="listing-meta">
                    <span>{r.owner_username}</span>
                    <span className={r.is_free ? "listing-price is-free" : "listing-price"}>
                      {r.is_free ? "無料" : `${r.price_credits.toLocaleString()} cr`}
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ReviewsSection({
  listingId,
  isOwnListing,
  isLoggedIn,
}: {
  listingId: string;
  isOwnListing: boolean;
  isLoggedIn: boolean;
}) {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [stars, setStars] = useState(5);
  const [text, setText] = useState("");
  const [posting, setPosting] = useState(false);

  const { data: reviews, isLoading } = useQuery({
    queryKey: ["reviews", listingId],
    queryFn: () => marketplaceService.listReviews(listingId),
  });

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setPosting(true);
    try {
      await marketplaceService.postReview(listingId, stars, text);
      setText("");
      queryClient.invalidateQueries({ queryKey: ["reviews", listingId] });
      queryClient.invalidateQueries({ queryKey: ["listing", listingId] });
      show("レビューを投稿しました");
    } catch (err) {
      show(apiErrorMessage(err, "レビューの投稿に失敗しました"), "error");
    } finally {
      setPosting(false);
    }
  }

  async function handleHelpful(reviewId: string, helpful: boolean) {
    try {
      await marketplaceService.voteReviewHelpful(reviewId, helpful);
      queryClient.invalidateQueries({ queryKey: ["reviews", listingId] });
    } catch (err) {
      show(apiErrorMessage(err, "投票に失敗しました"), "error");
    }
  }

  return (
    <section style={{ marginTop: 12 }}>
      <h2 style={{ fontSize: 18 }}>レビュー</h2>

      {isLoggedIn && !isOwnListing && (
        <form onSubmit={handleSubmit} className="card card-pad" style={{ maxWidth: 480, marginBottom: 20 }}>
          <div className="field">
            <label>評価</label>
            <div style={{ marginTop: 4 }}>
              <StarRating value={stars} onChange={setStars} size={22} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="review-text">コメント（任意）</label>
            <textarea id="review-text" value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={2000} />
          </div>
          <button type="submit" className="btn btn-primary" disabled={posting}>
            {posting ? "投稿中..." : "レビューを投稿"}
          </button>
        </form>
      )}

      {isLoading ? (
        <CenterSpinner />
      ) : !reviews || reviews.items.length === 0 ? (
        <div className="empty-state">まだレビューがありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {reviews.items.map((r) => (
              <div key={r.review_id} className="row-item" style={{ alignItems: "flex-start" }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <strong>{r.username}</strong>
                    <StarRating value={r.stars} />
                    <span style={{ fontSize: 12, color: "var(--faint)" }}>
                      {new Date(r.created_at).toLocaleDateString("ja-JP")}
                    </span>
                  </div>
                  {r.text && <p style={{ margin: "6px 0 0" }}>{r.text}</p>}
                  <ReviewReplies reviewId={r.review_id} isLoggedIn={isLoggedIn} />
                </div>
                {isLoggedIn && (
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                    <button className="btn btn-ghost btn-sm" onClick={() => handleHelpful(r.review_id, true)}>
                      役に立った（{r.helpful_count}）
                    </button>
                    <ReportReviewButton reviewId={r.review_id} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function ReportReviewButton({ reviewId }: { reviewId: string }) {
  const { show } = useToast();
  const [showForm, setShowForm] = useState(false);
  const [reason, setReason] = useState<string>(marketplaceService.REVIEW_REPORT_REASONS[0].value);
  const [busy, setBusy] = useState(false);

  async function handleSubmit() {
    setBusy(true);
    try {
      await marketplaceService.reportReview(reviewId, reason);
      show("通報を受け付けました");
      setShowForm(false);
    } catch (err) {
      show(apiErrorMessage(err, "通報に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  if (!showForm) {
    return (
      <button className="btn btn-ghost btn-sm" style={{ fontSize: 11 }} onClick={() => setShowForm(true)}>
        通報
      </button>
    );
  }

  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
      <select
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        style={{ fontSize: 11, padding: "2px 4px" }}
        aria-label="レビューの通報理由"
      >
        {marketplaceService.REVIEW_REPORT_REASONS.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>
      <button className="btn btn-secondary btn-sm" style={{ fontSize: 11 }} onClick={handleSubmit} disabled={busy}>
        送信
      </button>
      <button className="btn btn-ghost btn-sm" style={{ fontSize: 11 }} onClick={() => setShowForm(false)}>
        取消
      </button>
    </div>
  );
}

function ReviewReplies({ reviewId, isLoggedIn }: { reviewId: string; isLoggedIn: boolean }) {
  const { user } = useAuth();
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [replyText, setReplyText] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [posting, setPosting] = useState(false);

  // The replies endpoint requires auth, so anonymous visitors just don't see
  // the thread rather than triggering 401s on every review.
  const { data: replies } = useQuery({
    queryKey: ["review-replies", reviewId],
    queryFn: () => marketplaceService.getReviewReplies(reviewId),
    enabled: isLoggedIn,
  });

  async function handlePost(e: FormEvent) {
    e.preventDefault();
    if (!replyText.trim()) return;
    setPosting(true);
    try {
      await marketplaceService.postReviewReply(reviewId, replyText);
      setReplyText("");
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["review-replies", reviewId] });
      show("返信を投稿しました");
    } catch (err) {
      show(apiErrorMessage(err, "返信の投稿に失敗しました"), "error");
    } finally {
      setPosting(false);
    }
  }

  async function handleDelete(replyId: string) {
    try {
      await marketplaceService.deleteReviewReply(reviewId, replyId);
      queryClient.invalidateQueries({ queryKey: ["review-replies", reviewId] });
    } catch (err) {
      show(apiErrorMessage(err, "返信の削除に失敗しました"), "error");
    }
  }

  if (!isLoggedIn) return null;

  return (
    <div style={{ marginTop: 8 }}>
      {replies && replies.items.length > 0 && (
        <div style={{ borderLeft: "2px solid var(--border)", paddingLeft: 12, display: "grid", gap: 8 }}>
          {replies.items.map((reply) => (
            <div key={reply.reply_id} style={{ fontSize: 13 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <strong>{reply.username}</strong>
                <span style={{ fontSize: 11, color: "var(--faint)" }}>
                  {new Date(reply.created_at).toLocaleDateString("ja-JP")}
                </span>
                {user?.user_id === reply.user_id && (
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ fontSize: 11, padding: "1px 6px" }}
                    onClick={() => handleDelete(reply.reply_id)}
                    aria-label="この返信を削除"
                  >
                    削除
                  </button>
                )}
              </div>
              <p style={{ margin: "2px 0 0" }}>{reply.text}</p>
            </div>
          ))}
        </div>
      )}
      {showForm ? (
        <form onSubmit={handlePost} style={{ display: "flex", gap: 8, marginTop: 6 }}>
          <input
            type="text"
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            placeholder="返信を入力..."
            maxLength={1000}
            style={{ flex: 1, fontSize: 13, padding: "6px 10px" }}
            aria-label="レビューへの返信"
          />
          <button type="submit" className="btn btn-secondary btn-sm" disabled={posting}>
            {posting ? "送信中..." : "送信"}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>
            キャンセル
          </button>
        </form>
      ) : (
        <button
          className="btn btn-ghost btn-sm"
          style={{ marginTop: 4, fontSize: 12 }}
          onClick={() => setShowForm(true)}
        >
          返信する
        </button>
      )}
    </div>
  );
}

function RatingDistributionSection({ listingId }: { listingId: string }) {
  const { data } = useQuery({
    queryKey: ["rating-distribution", listingId],
    queryFn: () => marketplaceService.getRatingDistribution(listingId),
  });

  if (!data || data.total_ratings === 0) return null;

  const max = Math.max(...Object.values(data.distribution), 1);

  return (
    <section style={{ marginTop: 12 }}>
      <h2 style={{ fontSize: 18 }}>評価の分布</h2>
      <div className="card card-pad" style={{ maxWidth: 480 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
          <span style={{ fontSize: 28, fontWeight: 700 }}>{data.average_rating.toFixed(1)}</span>
          <StarRating value={Math.round(data.average_rating)} />
          <span style={{ fontSize: 13, color: "var(--muted)" }}>{data.total_ratings} 件の評価</span>
        </div>
        {[5, 4, 3, 2, 1].map((star) => {
          const count = data.distribution[String(star)] ?? 0;
          const pct = Math.round((count / max) * 100);
          return (
            <div key={star} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, padding: "2px 0" }}>
              <span style={{ width: 32, color: "var(--muted)" }}>{star} ★</span>
              <div style={{ flex: 1, height: 8, background: "var(--surface-2)", borderRadius: 4, overflow: "hidden" }}>
                <div style={{ width: `${pct}%`, height: "100%", background: "var(--accent)" }} />
              </div>
              <span style={{ width: 28, textAlign: "right", color: "var(--muted)" }}>{count}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function VersionHistorySection({ listingId, isOwnListing }: { listingId: string; isOwnListing: boolean }) {
  const { show } = useToast();
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [changelog, setChangelog] = useState("");
  const [parametersText, setParametersText] = useState("");
  const [busy, setBusy] = useState(false);

  const { data } = useQuery({
    queryKey: ["listing-versions", listingId],
    queryFn: () => marketplaceService.getListingVersions(listingId),
  });

  async function handlePublish(e: FormEvent) {
    e.preventDefault();
    if (!changelog.trim()) return;
    let parameters: Record<string, unknown> | undefined;
    if (parametersText.trim()) {
      try {
        parameters = JSON.parse(parametersText);
      } catch {
        show("パラメータは有効なJSON形式で入力してください", "error");
        return;
      }
    }
    setBusy(true);
    try {
      await marketplaceService.publishListingVersion(listingId, { changelog, parameters });
      setChangelog("");
      setParametersText("");
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["listing-versions", listingId] });
      queryClient.invalidateQueries({ queryKey: ["listing", listingId] });
      show("新しいバージョンを公開しました");
    } catch (err) {
      show(apiErrorMessage(err, "バージョンの公開に失敗しました"), "error");
    } finally {
      setBusy(false);
    }
  }

  // A listing always has v1 from publish; only show the section when there's
  // history worth showing OR the owner can add to it.
  if ((!data || data.items.length <= 1) && !isOwnListing) return null;

  return (
    <section style={{ marginTop: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h2 style={{ fontSize: 18 }}>バージョン履歴</h2>
        {isOwnListing && !showForm && (
          <button className="btn btn-secondary btn-sm" onClick={() => setShowForm(true)}>
            新バージョンを公開
          </button>
        )}
      </div>

      {showForm && (
        <form onSubmit={handlePublish} className="card card-pad" style={{ maxWidth: 480, marginBottom: 16 }}>
          <div className="field">
            <label htmlFor="version-changelog">変更内容</label>
            <textarea
              id="version-changelog"
              value={changelog}
              onChange={(e) => setChangelog(e.target.value)}
              rows={2}
              maxLength={1000}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="version-parameters">更新後のパラメータ（JSON、任意）</label>
            <textarea
              id="version-parameters"
              value={parametersText}
              onChange={(e) => setParametersText(e.target.value)}
              rows={3}
              placeholder="空欄なら現在のパラメータを維持"
              style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}
            />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
              {busy ? "公開中..." : "公開する"}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>
              キャンセル
            </button>
          </div>
        </form>
      )}

      {data && data.items.length > 0 && (
        <div className="card card-pad">
          <div className="row-list">
            {[...data.items].reverse().map((v) => (
              <div key={v.version_id} className="row-item" style={{ alignItems: "flex-start" }}>
                <div>
                  <strong>v{v.version_number}</strong>
                  <span style={{ fontSize: 12, color: "var(--faint)", marginLeft: 8 }}>
                    {new Date(v.created_at).toLocaleDateString("ja-JP")}
                  </span>
                  <p style={{ margin: "4px 0 0", fontSize: 14 }}>{v.changelog}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
