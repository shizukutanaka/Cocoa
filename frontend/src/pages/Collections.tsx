import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import * as collectionsService from "../services/collectionsService";
import { CenterSpinner } from "../components/Spinner";
import { useToast } from "../hooks/useToast";
import { apiErrorMessage } from "../services/apiClient";

export function Collections() {
  const queryClient = useQueryClient();
  const { show } = useToast();
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["my-collections"],
    queryFn: () => collectionsService.myCollections(50, 0),
  });

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      await collectionsService.createCollection(name.trim());
      setName("");
      queryClient.invalidateQueries({ queryKey: ["my-collections"] });
    } catch (err) {
      show(apiErrorMessage(err, "作成に失敗しました"), "error");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <h1>コレクション</h1>

      <form onSubmit={handleCreate} className="filters-bar">
        <input type="text" placeholder="新しいコレクション名" value={name} onChange={(e) => setName(e.target.value)} />
        <button type="submit" className="btn btn-primary" disabled={creating}>
          作成
        </button>
      </form>

      {isLoading ? (
        <CenterSpinner />
      ) : !data || data.items.length === 0 ? (
        <div className="empty-state">コレクションはまだありません。</div>
      ) : (
        <div className="listing-grid">
          {data.items.map((col) => (
            <Link key={col.collection_id} to={`/collections/${col.collection_id}`} className="card card-pad listing-card">
              <div className="listing-name">{col.name}</div>
              <div className="listing-meta">
                <span>{col.item_count} 件</span>
                <span className="badge">{col.is_public ? "公開" : "非公開"}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
