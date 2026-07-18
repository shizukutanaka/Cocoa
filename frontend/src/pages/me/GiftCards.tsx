import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import * as giftCardService from "../../services/giftCardService";
import { apiErrorMessage } from "../../services/apiClient";
import { useToast } from "../../hooks/useToast";
import { CenterSpinner } from "../../components/Spinner";

export function GiftCards() {
  const { show } = useToast();
  const queryClient = useQueryClient();

  const { data: cards, isLoading } = useQuery({
    queryKey: ["gift-cards"],
    queryFn: () => giftCardService.myGiftCards(50, 0),
  });

  const [amount, setAmount] = useState(1000);
  const [message, setMessage] = useState("");
  const [purchasing, setPurchasing] = useState(false);
  const [redeemCode, setRedeemCode] = useState("");
  const [redeeming, setRedeeming] = useState(false);
  const [lookup, setLookup] = useState<giftCardService.GiftCardLookup | null>(null);
  const [lookingUp, setLookingUp] = useState(false);

  async function handlePurchase(e: FormEvent) {
    e.preventDefault();
    setPurchasing(true);
    try {
      const card = await giftCardService.purchaseGiftCard(amount, message);
      show(`ギフトカードを作成しました。コード: ${card.code}`);
      setMessage("");
      queryClient.invalidateQueries({ queryKey: ["gift-cards"] });
      queryClient.invalidateQueries({ queryKey: ["credits-balance"] });
    } catch (err) {
      show(apiErrorMessage(err, "ギフトカードの購入に失敗しました"), "error");
    } finally {
      setPurchasing(false);
    }
  }

  async function handleLookup() {
    const code = redeemCode.trim();
    if (!code) return;
    setLookingUp(true);
    setLookup(null);
    try {
      const result = await giftCardService.lookupGiftCard(code);
      setLookup(result);
    } catch (err) {
      show(apiErrorMessage(err, "ギフトカードが見つかりません"), "error");
    } finally {
      setLookingUp(false);
    }
  }

  async function handleRedeem(e: FormEvent) {
    e.preventDefault();
    setRedeeming(true);
    try {
      const result = await giftCardService.redeemGiftCard(redeemCode.trim());
      show(`${result.credits_received.toLocaleString()} クレジットを受け取りました`);
      setRedeemCode("");
      setLookup(null);
      queryClient.invalidateQueries({ queryKey: ["credits-balance"] });
    } catch (err) {
      show(apiErrorMessage(err, "ギフトカードの使用に失敗しました"), "error");
    } finally {
      setRedeeming(false);
    }
  }

  return (
    <div>
      <h1>ギフトカード</h1>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 24 }}>
        <section className="card card-pad">
          <h2 style={{ fontSize: 16 }}>購入する</h2>
          <form onSubmit={handlePurchase}>
            <div className="field">
              <label htmlFor="gc-amount">金額（クレジット）</label>
              <input
                id="gc-amount"
                type="number"
                min={1}
                value={amount}
                onChange={(e) => setAmount(Number(e.target.value))}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="gc-message">メッセージ（任意）</label>
              <input id="gc-message" value={message} onChange={(e) => setMessage(e.target.value)} maxLength={200} />
            </div>
            <button type="submit" className="btn btn-primary" disabled={purchasing}>
              {purchasing ? "作成中..." : "購入する"}
            </button>
          </form>
        </section>

        <section className="card card-pad">
          <h2 style={{ fontSize: 16 }}>コードを使用する</h2>
          <form onSubmit={handleRedeem}>
            <div className="field">
              <label htmlFor="gc-code">ギフトカードコード</label>
              <input
                id="gc-code"
                value={redeemCode}
                onChange={(e) => {
                  setRedeemCode(e.target.value);
                  setLookup(null);
                }}
                required
              />
            </div>

            {lookup && (
              <div
                className={lookup.is_valid ? "card card-pad" : "form-error-banner"}
                style={{ marginBottom: 12, fontSize: 13 }}
              >
                {lookup.is_valid ? (
                  <>
                    <strong>{lookup.amount.toLocaleString()} クレジット</strong> のギフトカードです。
                    {lookup.expires_at && (
                      <div style={{ color: "var(--muted)" }}>
                        有効期限: {new Date(lookup.expires_at).toLocaleDateString("ja-JP")}
                      </div>
                    )}
                  </>
                ) : lookup.is_redeemed ? (
                  "このギフトカードは既に使用済みです。"
                ) : (
                  "このギフトカードは無効または期限切れです。"
                )}
              </div>
            )}

            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={handleLookup}
                disabled={lookingUp || !redeemCode.trim()}
              >
                {lookingUp ? "確認中..." : "確認"}
              </button>
              <button
                type="submit"
                className="btn btn-secondary"
                disabled={redeeming || (lookup !== null && !lookup.is_valid)}
              >
                {redeeming ? "処理中..." : "使用する"}
              </button>
            </div>
          </form>
        </section>
      </div>

      <h2 style={{ fontSize: 16 }}>購入したギフトカード</h2>
      {isLoading ? (
        <CenterSpinner />
      ) : !cards || cards.items.length === 0 ? (
        <div className="empty-state">まだ購入したギフトカードはありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {cards.items.map((card) => (
              <div key={card.card_id} className="row-item">
                <div>
                  <div style={{ fontWeight: 600, fontFamily: "var(--font-mono)" }}>{card.code}</div>
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>
                    {card.message || "（メッセージなし）"} · {new Date(card.created_at).toLocaleDateString("ja-JP")}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span className="listing-price">{card.amount.toLocaleString()} cr</span>
                  <span className={card.is_redeemed ? "badge" : "badge badge-success"}>
                    {card.is_redeemed ? "使用済み" : "未使用"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
