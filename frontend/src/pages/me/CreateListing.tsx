import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import * as marketplaceService from "../../services/marketplaceService";
import { apiErrorMessage } from "../../services/apiClient";
import { useToast } from "../../hooks/useToast";

export function CreateListing() {
  const { show } = useToast();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [platform, setPlatform] = useState("");
  const [tags, setTags] = useState("");
  const [thumbnailUrl, setThumbnailUrl] = useState("");
  const [isFree, setIsFree] = useState(true);
  const [priceCredits, setPriceCredits] = useState(0);
  const [licenseType, setLicenseType] = useState("personal");
  const [parametersText, setParametersText] = useState("{}");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");

    let parameters: Record<string, unknown>;
    try {
      parameters = JSON.parse(parametersText || "{}");
    } catch {
      setError("パラメータは有効なJSON形式で入力してください");
      return;
    }

    setBusy(true);
    try {
      const listing = await marketplaceService.publishListing({
        avatar_id: crypto.randomUUID(),
        name,
        description,
        category,
        platform,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        thumbnail_url: thumbnailUrl,
        is_free: isFree,
        price_credits: isFree ? 0 : priceCredits,
        license_type: licenseType,
        parameters,
      });
      show("出品しました");
      navigate(`/listings/${listing.listing_id}`);
    } catch (err) {
      setError(apiErrorMessage(err, "出品に失敗しました"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1>新規出品</h1>
      <div className="card card-pad" style={{ maxWidth: 560 }}>
        {error && <div className="form-error-banner">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="name">名前</label>
            <input id="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} required />
          </div>
          <div className="field">
            <label htmlFor="description">説明</label>
            <textarea id="description" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} maxLength={2000} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="field">
              <label htmlFor="category">カテゴリ</label>
              <input id="category" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="humanoid, animal など" />
            </div>
            <div className="field">
              <label htmlFor="platform">プラットフォーム</label>
              <input id="platform" value={platform} onChange={(e) => setPlatform(e.target.value)} placeholder="vrchat, resonite など" />
            </div>
          </div>
          <div className="field">
            <label htmlFor="tags">タグ（カンマ区切り）</label>
            <input id="tags" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="casual, cute, fantasy" />
          </div>
          <div className="field">
            <label htmlFor="thumbnail">サムネイルURL（任意）</label>
            <input id="thumbnail" value={thumbnailUrl} onChange={(e) => setThumbnailUrl(e.target.value)} />
          </div>

          <div className="field">
            <label>
              <input type="checkbox" checked={isFree} onChange={(e) => setIsFree(e.target.checked)} style={{ marginRight: 6 }} />
              無料で配布する
            </label>
          </div>
          {!isFree && (
            <div className="field">
              <label htmlFor="price">価格（クレジット）</label>
              <input
                id="price"
                type="number"
                min={0}
                value={priceCredits}
                onChange={(e) => setPriceCredits(Number(e.target.value))}
              />
            </div>
          )}

          <div className="field">
            <label htmlFor="license">ライセンス種別</label>
            <select id="license" value={licenseType} onChange={(e) => setLicenseType(e.target.value)}>
              <option value="personal">個人利用のみ</option>
              <option value="cc_by">CC BY（表示）</option>
              <option value="cc_by_sa">CC BY-SA（表示-継承）</option>
              <option value="commercial">商用利用可</option>
              <option value="custom">カスタム</option>
            </select>
          </div>

          <div className="field">
            <label htmlFor="parameters">アバターパラメータ（JSON）</label>
            <textarea
              id="parameters"
              value={parametersText}
              onChange={(e) => setParametersText(e.target.value)}
              rows={5}
              style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}
            />
          </div>

          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? "出品中..." : "出品する"}
          </button>
        </form>
      </div>
    </div>
  );
}
