"""
Avatar collections — let users organize avatars (owned or bookmarked) into
named, optionally-public collections (think playlists / folders).

Pure stdlib, thread-safe, in-memory. Swap the store for a DB table in prod.
"""
from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from .pagination import normalize_pagination
except ImportError:  # pragma: no cover - support flat import in tests
    from pagination import normalize_pagination

_MAX_COLLECTIONS_PER_USER = 100
_MAX_ITEMS_PER_COLLECTION = 500


@dataclass
class Collection:
    collection_id: str
    owner_id: str
    name: str
    description: str = ""
    is_public: bool = False
    item_ids: List[str] = field(default_factory=list)  # listing_id / avatar_id
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "collection_id": self.collection_id,
            "owner_id": self.owner_id,
            "name": self.name,
            "description": self.description,
            "is_public": self.is_public,
            "item_ids": list(self.item_ids),
            "item_count": len(self.item_ids),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class CollectionStore:
    """Thread-safe in-memory collection store."""

    def __init__(self):
        self._collections: Dict[str, Collection] = {}
        self._lock = threading.Lock()

    def create(self, owner_id: str, name: str, description: str = "", is_public: bool = False) -> Collection:
        name = name.strip()
        if not name:
            raise ValueError("コレクション名は必須です")
        with self._lock:
            owned = [c for c in self._collections.values() if c.owner_id == owner_id]
            if len(owned) >= _MAX_COLLECTIONS_PER_USER:
                raise ValueError(f"コレクション数の上限（{_MAX_COLLECTIONS_PER_USER}）に達しました")
            col = Collection(
                collection_id=secrets.token_hex(10),
                owner_id=owner_id,
                name=name[:100],
                description=description.strip()[:500],
                is_public=is_public,
            )
            self._collections[col.collection_id] = col
            return col

    def get(self, collection_id: str) -> Optional[Collection]:
        with self._lock:
            return self._collections.get(collection_id)

    def update(
        self,
        collection_id: str,
        requester_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_public: Optional[bool] = None,
    ) -> Collection:
        with self._lock:
            col = self._require_owned(collection_id, requester_id)
            if name is not None:
                clean = name.strip()
                if not clean:
                    raise ValueError("コレクション名は必須です")
                col.name = clean[:100]
            if description is not None:
                col.description = description.strip()[:500]
            if is_public is not None:
                col.is_public = is_public
            col.updated_at = datetime.now(timezone.utc)
            return col

    def delete(self, collection_id: str, requester_id: str) -> bool:
        with self._lock:
            col = self._collections.get(collection_id)
            if not col:
                return False
            if col.owner_id != requester_id:
                raise PermissionError("自分のコレクションのみ削除できます")
            del self._collections[collection_id]
            return True

    def add_item(self, collection_id: str, requester_id: str, item_id: str) -> Collection:
        with self._lock:
            col = self._require_owned(collection_id, requester_id)
            if len(col.item_ids) >= _MAX_ITEMS_PER_COLLECTION:
                raise ValueError(f"アイテム数の上限（{_MAX_ITEMS_PER_COLLECTION}）に達しました")
            if item_id not in col.item_ids:
                col.item_ids.append(item_id)
                col.updated_at = datetime.now(timezone.utc)
            return col

    def remove_item(self, collection_id: str, requester_id: str, item_id: str) -> Collection:
        with self._lock:
            col = self._require_owned(collection_id, requester_id)
            if item_id in col.item_ids:
                col.item_ids.remove(item_id)
                col.updated_at = datetime.now(timezone.utc)
            return col

    def list_user_collections(self, owner_id: str, *, requester_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List a user's collections. If requester != owner, only public ones."""
        with self._lock:
            cols = [c for c in self._collections.values() if c.owner_id == owner_id]
        if requester_id != owner_id:
            cols = [c for c in cols if c.is_public]
        cols.sort(key=lambda c: c.updated_at, reverse=True)
        return [c.to_dict() for c in cols]

    def get_public(self, collection_id: str, requester_id: Optional[str] = None) -> Optional[Collection]:
        """Return a collection only if public or owned by requester."""
        col = self._collections.get(collection_id)
        if not col:
            return None
        if col.is_public or col.owner_id == requester_id:
            return col
        return None

    def browse_public(
        self,
        query: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Return paginated public collections, optionally filtered by name/description query."""
        with self._lock:
            items = [c for c in self._collections.values() if c.is_public]
        if query:
            q = query.lower()
            items = [c for c in items if q in c.name.lower() or q in c.description.lower()]
        items.sort(key=lambda c: c.updated_at, reverse=True)
        total = len(items)
        offset, limit = normalize_pagination(offset, limit)
        page = items[offset : offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [c.to_dict() for c in page],
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            cols = list(self._collections.values())
        return {
            "total_collections": len(cols),
            "public_collections": sum(1 for c in cols if c.is_public),
            "total_items": sum(len(c.item_ids) for c in cols),
        }

    # --- internal ---
    def _require_owned(self, collection_id: str, requester_id: str) -> Collection:
        col = self._collections.get(collection_id)
        if not col:
            raise ValueError("コレクションが見つかりません")
        if col.owner_id != requester_id:
            raise PermissionError("自分のコレクションのみ編集できます")
        return col


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_store: Optional[CollectionStore] = None


def get_collection_store() -> CollectionStore:
    global _store
    if _store is None:
        _store = CollectionStore()
    return _store
