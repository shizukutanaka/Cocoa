import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import * as collectionsService from "../services/collectionsService";
import { CenterSpinner } from "../components/Spinner";
import { useToast } from "../hooks/useToast";
import { apiErrorMessage } from "../services/apiClient";

export function CollectionDetail() {
  const { collectionId } = useParams<{ collectionId: string }>();
  const queryClient = useQueryClient();
  const { show } = useToast();

  const { data: collection, isLoading: loadingCollection } = useQuery({
    queryKey: ["collection", collectionId],
    queryFn: () => collectionsService.getCollection(collectionId!),
    enabled: !!collectionId,
  });

  const { data: items, isLoading: loadingItems } = useQuery({
    queryKey: ["collection-items", collectionId],
    queryFn: () => collectionsService.getCollectionItems(collectionId!, 50, 0),
    enabled: !!collectionId,
  });

  async function handleRemove(itemId: string) {
    if (!collectionId) return;
    try {
      await collectionsService.removeItemFromCollection(collectionId, itemId);
      queryClient.invalidateQueries({ queryKey: ["collection-items", collectionId] });
    } catch (err) {
      show(apiErrorMessage(err, "削除に失敗しました"), "error");
    }
  }

  if (loadingCollection || loadingItems) return <CenterSpinner />;
  if (!collection) return <div className="empty-state">コレクションが見つかりませんでした。</div>;

  return (
    <div>
      <h1>{collection.name}</h1>
      {collection.description && <p style={{ color: "var(--muted)" }}>{collection.description}</p>}

      {!items || items.items.length === 0 ? (
        <div className="empty-state">このコレクションにはアイテムがありません。</div>
      ) : (
        <div className="card card-pad">
          <div className="row-list">
            {items.items.map((item) => (
              <div key={item.listing_id} className="row-item">
                <div>
                  {item.delisted ? (
                    <span style={{ color: "var(--faint)" }}>（削除されたリスティング）</span>
                  ) : (
                    <Link to={`/listings/${item.listing_id}`}>{item.listing_name}</Link>
                  )}
                  {item.is_sold_out && <span className="badge badge-warning" style={{ marginLeft: 8 }}>在庫切れ</span>}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  {item.current_price != null && <span className="listing-price">{item.current_price.toLocaleString()} cr</span>}
                  <button className="btn btn-ghost btn-sm" onClick={() => handleRemove(item.listing_id)}>
                    削除
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
