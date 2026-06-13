"""
Saved Search Presets

Users can persist named search queries with filters for quick reuse.
"""
from __future__ import annotations

import contextlib
import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_PER_USER = int(__import__("os").getenv("SAVED_SEARCH_MAX_PER_USER", "50"))


@dataclass
class SavedSearch:
    search_id: str
    user_id: str
    name: str
    query: str
    filters: Dict[str, Any]  # category, platform, tags, sort_by
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: Optional[datetime] = None
    use_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "search_id": self.search_id,
            "user_id": self.user_id,
            "name": self.name,
            "query": self.query,
            "filters": dict(self.filters),
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "use_count": self.use_count,
        }


class SavedSearchStore:
    """Thread-safe in-memory store for saved search presets."""

    def __init__(self, max_per_user: int = _MAX_PER_USER):
        self._searches: Dict[str, SavedSearch] = {}  # search_id → SavedSearch
        self._user_index: Dict[str, List[str]] = {}   # user_id → [search_id, ...]
        self._lock = threading.Lock()
        self._max_per_user = max_per_user

    # --- CRUD ---

    def create(
        self,
        user_id: str,
        name: str,
        query: str = "",
        filters: Optional[Dict[str, Any]] = None,
    ) -> SavedSearch:
        name = name.strip()[:80]
        if not name:
            raise ValueError("保存検索名を入力してください")
        with self._lock:
            user_ids = self._user_index.setdefault(user_id, [])
            if len(user_ids) >= self._max_per_user:
                raise ValueError(f"保存検索の上限 ({self._max_per_user} 件) に達しています")
            search_id = secrets.token_hex(8)
            ss = SavedSearch(
                search_id=search_id,
                user_id=user_id,
                name=name,
                query=query.strip(),
                filters=filters or {},
            )
            self._searches[search_id] = ss
            user_ids.append(search_id)
            logger.debug("SavedSearch created: %s for user %s", search_id, user_id)
            return ss

    def list(self, user_id: str) -> List[SavedSearch]:
        with self._lock:
            ids = self._user_index.get(user_id, [])
            return [self._searches[sid] for sid in ids if sid in self._searches]

    def get(self, user_id: str, search_id: str) -> Optional[SavedSearch]:
        with self._lock:
            ss = self._searches.get(search_id)
            return ss if ss and ss.user_id == user_id else None

    def delete(self, user_id: str, search_id: str) -> bool:
        with self._lock:
            ss = self._searches.get(search_id)
            if not ss or ss.user_id != user_id:
                return False
            del self._searches[search_id]
            ids = self._user_index.get(user_id, [])
            with contextlib.suppress(ValueError):
                ids.remove(search_id)
            return True

    def record_use(self, user_id: str, search_id: str) -> bool:
        with self._lock:
            ss = self._searches.get(search_id)
            if not ss or ss.user_id != user_id:
                return False
            ss.last_used = datetime.now(timezone.utc)
            ss.use_count += 1
            return True

    def update(
        self,
        user_id: str,
        search_id: str,
        name: Optional[str] = None,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Optional[SavedSearch]:
        with self._lock:
            ss = self._searches.get(search_id)
            if not ss or ss.user_id != user_id:
                return None
            if name is not None:
                name = name.strip()[:80]
                if name:
                    ss.name = name
            if query is not None:
                ss.query = query.strip()
            if filters is not None:
                ss.filters = dict(filters)
            return ss

    def stats(self, user_id: str) -> Dict[str, Any]:
        searches = self.list(user_id)
        return {
            "total": len(searches),
            "max_allowed": self._max_per_user,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_store: Optional[SavedSearchStore] = None


def get_saved_search_store() -> SavedSearchStore:
    global _store
    if _store is None:
        _store = SavedSearchStore()
    return _store
