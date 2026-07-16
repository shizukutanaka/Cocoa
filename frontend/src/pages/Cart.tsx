import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { checkout, getCart, removeFromCart, setCartItemPromo } from "../services/cartService";
import { lookupPromoCode } from "../services/marketplaceService";
import { newIdempotencyKey } from "../services/apiClient";
import { CenterSpinner } from "../components/Spinner";
import { useToast } from "../hooks/useToast";
import { usePageTitle } from "../hooks/usePageTitle";
import { apiErrorMessage } from "../services/apiClient";
import type { PromoLookup } from "../types/api";

export function CartPage() {
  usePageTitle("カート");
  const queryClient = useQueryClient();
  const { show } = useToast();
  const navigate = useNavigate();
  const [checkingOut, setCheckingOut] = useState(false);
  const [promoInputs, setPromoInputs] = useState<Record<string, string>>({});
  // Validated discount previews per listing (the discount itself is applied at
  // checkout time by the backend; this is the buyer-facing confirmation).
  const [promoPreviews, setPromoPreviews] = useState<Record<string, PromoLookup>>({});
  // Stable for the lifetime of this cart view: retrying the SAME checkout
  // attempt (e.g. after a network timeout) must reuse the same key so the
  // backend's idempotency store returns the original order instead of
  // charging twice -- see main/api_server.py's checkout_cart.
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey);

  const { data: cart, isLoading } = useQuery({ queryKey: ["cart"], queryFn: getCart });

  // Rebuild discount previews for items whose promo_code survived a reload --
  // the cart stores the code but its subtotal_credits is pre-discount (the
  // discount itself is computed at checkout), so without this the row and the
  // total would silently show full price again after a refresh.
  useEffect(() => {
    if (!cart) return;
    for (const item of cart.items) {
      if (item.promo_code && !item.is_free && !promoPreviews[item.listing_id]) {
        lookupPromoCode(item.listing_id, item.promo_code)
          .then((preview) =>
            setPromoPreviews((prev) => ({ ...prev, [item.listing_id]: preview }))
          )
          .catch(() => {
            /* code no longer valid -- keep showing the undiscounted price */
          });
      }
    }
  }, [cart]);

  // Display total: backend subtotal minus validated per-item discounts.
  const discountTotal = cart
    ? cart.items.reduce((sum, item) => {
        const p = promoPreviews[item.listing_id];
        return p ? sum + (p.original_price - p.discounted_price) : sum;
      }, 0)
    : 0;

  async function handleRemove(listingId: string) {
    await removeFromCart(listingId);
    queryClient.invalidateQueries({ queryKey: ["cart"] });
  }

  async function handleApplyPromo(listingId: string) {
    const promoCode = (promoInputs[listingId] ?? "").trim();
    if (!promoCode) return;
    try {
      // Validate first so a bad code errors here instead of surfacing as a
      // silent no-discount at checkout time.
      const preview = await lookupPromoCode(listingId, promoCode);
      await setCartItemPromo(listingId, promoCode);
      setPromoPreviews((prev) => ({ ...prev, [listingId]: preview }));
      queryClient.invalidateQueries({ queryKey: ["cart"] });
      show(`${preview.discount_percent}% OFF が適用されます`);
    } catch (err) {
      show(apiErrorMessage(err, "プロモコードが無効です"), "error");
    }
  }

  async function handleCheckout() {
    setCheckingOut(true);
    try {
      const result = await checkout(idempotencyKey);
      if (result.success) {
        show("購入が完了しました");
        setIdempotencyKey(newIdempotencyKey());
        queryClient.invalidateQueries({ queryKey: ["cart"] });
        navigate(`/me/orders`);
      } else {
        show("一部のアイテムを購入できませんでした", "error");
        queryClient.invalidateQueries({ queryKey: ["cart"] });
      }
    } catch (err) {
      show(apiErrorMessage(err, "チェックアウトに失敗しました"), "error");
    } finally {
      setCheckingOut(false);
    }
  }

  if (isLoading) return <CenterSpinner />;
  if (!cart || cart.items.length === 0) {
    return (
      <div>
        <h1>カート</h1>
        <div className="empty-state">カートは空です。</div>
      </div>
    );
  }

  return (
    <div>
      <h1>カート</h1>
      <div className="card card-pad">
        <div className="row-list">
          {cart.items.map((item) => {
            const preview = promoPreviews[item.listing_id];
            return (
              <div key={item.listing_id} className="row-item">
                <div>
                  <div style={{ fontWeight: 600 }}>{item.name}</div>
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>{item.owner_username}</div>
                  {!item.is_free &&
                    (item.promo_code ? (
                      <div style={{ fontSize: 13, marginTop: 4 }}>
                        <span className="badge badge-success">コード適用: {item.promo_code}</span>
                      </div>
                    ) : (
                      <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                        <input
                          type="text"
                          placeholder="プロモコード"
                          aria-label={`「${item.name}」のプロモコード`}
                          value={promoInputs[item.listing_id] ?? ""}
                          onChange={(e) =>
                            setPromoInputs((prev) => ({
                              ...prev,
                              [item.listing_id]: e.target.value.toUpperCase(),
                            }))
                          }
                          style={{ fontSize: 13, padding: "4px 8px", width: 140 }}
                        />
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleApplyPromo(item.listing_id)}
                        >
                          適用
                        </button>
                      </div>
                    ))}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                  {preview ? (
                    <span className="listing-price">
                      <s style={{ color: "var(--faint)", fontWeight: 400 }}>
                        {preview.original_price.toLocaleString()} cr
                      </s>{" "}
                      <span style={{ color: "var(--success)" }}>
                        {preview.discounted_price.toLocaleString()} cr
                      </span>
                    </span>
                  ) : (
                    <span className="listing-price">
                      {item.is_free ? "無料" : `${item.price_credits.toLocaleString()} cr`}
                    </span>
                  )}
                  <button className="btn btn-ghost btn-sm" onClick={() => handleRemove(item.listing_id)}>
                    削除
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 20 }}>
        <div>
          <span style={{ color: "var(--muted)" }}>合計: </span>
          {discountTotal > 0 ? (
            <>
              <s style={{ color: "var(--faint)" }}>{cart.subtotal_credits.toLocaleString()} cr</s>{" "}
              <span style={{ fontSize: 20, fontWeight: 700, color: "var(--success)" }}>
                {(cart.subtotal_credits - discountTotal).toLocaleString()} cr
              </span>
            </>
          ) : (
            <span style={{ fontSize: 20, fontWeight: 700 }}>{cart.subtotal_credits.toLocaleString()} cr</span>
          )}
        </div>
        <button className="btn btn-primary" onClick={handleCheckout} disabled={checkingOut}>
          {checkingOut ? "処理中..." : "チェックアウト"}
        </button>
      </div>
    </div>
  );
}
