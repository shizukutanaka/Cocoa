import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import * as collectionsService from "../services/collectionsService";
import { getPublicProfile } from "../services/userService";
import { CenterSpinner } from "../components/Spinner";
import { useToast } from "../hooks/useToast";
import { usePageTitle } from "../hooks/usePageTitle";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { apiErrorMessage } from "../services/apiClient";

function OwnerLabel({ userId }: { userId: string }) {
  const { data } = useQuery({
    queryKey: ["public-profile", userId],
    queryFn: () => getPublicProfile(userId),
  });
  return <span>by {data?.display_name ?? "..."}</span>;
}

export function Collections() {
  usePageTitle("コレクション");
  const queryClient = useQueryClient();
  const { show } = useToast();
  const [tab, setTab] = useState<"mine" | "public">("mine");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [publicQuery, setPublicQuery] = useState("");
  const debouncedQuery = useDebouncedValue(publicQuery, 300);

  const { data, isLoading } = useQuery({
    queryKey: ["my-collections"],
    queryFn: () => collectionsService.myCollections(50, 0),
    enabled: tab === "mine",
  });

  const { data: publicData, isLoading: publicLoading } = useQuery({
    queryKey: ["public-collections", debouncedQuery],
    queryFn: () => collectionsService.browsePublicCollections(debouncedQuery, 30, 0),
    enabled: tab === "public",
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

      <div className="filters-bar" role="tablist" aria-label="コレクションの表示切り替え" style={{ marginBottom: 16 }}>
        <button
          className={tab === "mine" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "mine"}
          onClick={() => setTab("mine")}
        >
          自分のコレクション
        </button>
        <button
          className={tab === "public" ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
          role="tab"
          aria-selected={tab === "public"}
          onClick={() => setTab("public")}
        >
          公開コレクションを探す
        </button>
      </div>

      {tab === "mine" ? (
        <>
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
        </>
      ) : (
        <>
          <div className="filters-bar">
            <input
              type="text"
              placeholder="コレクション名・説明で検索"
              value={publicQuery}
              onChange={(e) => setPublicQuery(e.target.value)}
            />
          </div>

          {publicLoading ? (
            <CenterSpinner />
          ) : !publicData || publicData.items.length === 0 ? (
            <div className="empty-state">公開コレクションが見つかりませんでした。</div>
          ) : (
            <div className="listing-grid">
              {publicData.items.map((col) => (
                <Link key={col.collection_id} to={`/collections/${col.collection_id}`} className="card card-pad listing-card">
                  <div className="listing-name">{col.name}</div>
                  {col.description && (
                    <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 2 }}>{col.description}</div>
                  )}
                  <div className="listing-meta">
                    <OwnerLabel userId={col.owner_id} />
                    <span>{col.item_count} 件</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
