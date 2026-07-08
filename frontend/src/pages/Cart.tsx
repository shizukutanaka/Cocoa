import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { checkout, getCart, removeFromCart } from "../services/cartService";
import { newIdempotencyKey } from "../services/apiClient";
import { CenterSpinner } from "../components/Spinner";
import { useToast } from "../hooks/useToast";
import { apiErrorMessage } from "../services/apiClient";

export function CartPage() {
  const queryClient = useQueryClient();
  const { show } = useToast();
  const navigate = useNavigate();
  const [checkingOut, setCheckingOut] = useState(false);
  // Stable for the lifetime of this cart view: retrying the SAME checkout
  // attempt (e.g. after a network timeout) must reuse the same key so the
  // backend's idempotency store returns the original order instead of
  // charging twice -- see main/api_server.py's checkout_cart.
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey);

  const { data: cart, isLoading } = useQuery({ queryKey: ["cart"], queryFn: getCart });

  async function handleRemove(listingId: string) {
    await removeFromCart(listingId);
    queryClient.invalidateQueries({ queryKey: ["cart"] });
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
          {cart.items.map((item) => (
            <div key={item.listing_id} className="row-item">
              <div>
                <div style={{ fontWeight: 600 }}>{item.name}</div>
                <div style={{ fontSize: 13, color: "var(--muted)" }}>{item.owner_username}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                <span className="listing-price">{item.is_free ? "無料" : `${item.price_credits.toLocaleString()} cr`}</span>
                <button className="btn btn-ghost btn-sm" onClick={() => handleRemove(item.listing_id)}>
                  削除
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 20 }}>
        <div>
          <span style={{ color: "var(--muted)" }}>合計: </span>
          <span style={{ fontSize: 20, fontWeight: 700 }}>{cart.subtotal_credits.toLocaleString()} cr</span>
        </div>
        <button className="btn btn-primary" onClick={handleCheckout} disabled={checkingOut}>
          {checkingOut ? "処理中..." : "チェックアウト"}
        </button>
      </div>
    </div>
  );
}
