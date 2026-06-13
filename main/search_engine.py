"""
Avatar Search & Discovery Engine

Features:
- Full-text search over name, description, tags
- Multi-field filtering (category, VRC platform, parameter ranges)
- Faceted counts for sidebar UIs
- Sort by relevance, name, date, popularity
- Paginated results with cursor support
- Indexing pipeline (re-index from any dict source)
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from .pagination import normalize_pagination
except ImportError:  # pragma: no cover - support flat import in tests
    from pagination import normalize_pagination

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Document model
# ---------------------------------------------------------------------------
@dataclass
class SearchDocument:
    doc_id: str
    owner_id: str
    name: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    category: str = ""
    platform: str = ""   # e.g. "vrchat", "web", "ar"
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_public: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    score: float = 0.0   # populated by search

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "owner_id": self.owner_id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "category": self.category,
            "platform": self.platform,
            "is_public": self.is_public,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "score": self.score,
        }


# ---------------------------------------------------------------------------
# Tokenizer / scorer
# ---------------------------------------------------------------------------
_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "to",
    "は", "が", "の", "に", "を", "で", "と", "も", "や", "な",
}


def _tokenize(text: str) -> List[str]:
    text = text.lower()
    tokens = re.findall(r"[a-z0-9぀-鿿゠-ヿ]+", text)
    return [t for t in tokens if t not in _STOPWORDS and (len(t) >= 3 or any(c.isdigit() for c in t))]


def _tf_score(query_tokens: List[str], doc_tokens: List[str]) -> float:
    """Simple TF-based relevance score."""
    if not query_tokens or not doc_tokens:
        return 0.0
    doc_set = set(doc_tokens)
    hits = sum(1 for qt in query_tokens if qt in doc_set)
    return hits / len(query_tokens)


def _field_tokens(doc: SearchDocument) -> Dict[str, List[str]]:
    return {
        "name": _tokenize(doc.name),
        "description": _tokenize(doc.description),
        "tags": _tokenize(" ".join(doc.tags)),
        "category": _tokenize(doc.category),
    }


_FIELD_WEIGHTS = {"name": 3.0, "tags": 2.0, "category": 1.5, "description": 1.0}


# ---------------------------------------------------------------------------
# Search index
# ---------------------------------------------------------------------------
class SearchIndex:
    def __init__(self):
        self._docs: Dict[str, SearchDocument] = {}
        self._inverted: Dict[str, Dict[str, float]] = {}  # token → {doc_id: weight}
        self._query_log: List[str] = []  # raw queries, newest first (capped at 10_000)
        self._query_log_max = 10_000
        self._lock = threading.Lock()

    # --- Indexing ---

    def index(self, doc: SearchDocument) -> None:
        with self._lock:
            self._remove_from_inverted(doc.doc_id)
            self._docs[doc.doc_id] = doc
            field_toks = _field_tokens(doc)
            for fname, toks in field_toks.items():
                weight = _FIELD_WEIGHTS.get(fname, 1.0)
                for tok in toks:
                    if tok not in self._inverted:
                        self._inverted[tok] = {}
                    self._inverted[tok][doc.doc_id] = (
                        self._inverted[tok].get(doc.doc_id, 0) + weight
                    )

    def remove(self, doc_id: str) -> bool:
        with self._lock:
            if doc_id not in self._docs:
                return False
            self._remove_from_inverted(doc_id)
            del self._docs[doc_id]
            return True

    def _remove_from_inverted(self, doc_id: str) -> None:
        for tok_map in self._inverted.values():
            tok_map.pop(doc_id, None)

    # --- Search ---

    def search(
        self,
        query: str = "",
        *,
        owner_id: Optional[str] = None,
        public_only: bool = False,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        platform: Optional[str] = None,
        sort_by: str = "relevance",  # relevance | name | newest | oldest
        limit: int = 20,
        offset: int = 0,
        boost_owner_ids: Optional[List[str]] = None,  # personalization: followed creator IDs
    ) -> Dict[str, Any]:
        with self._lock:
            candidates = list(self._docs.values())

        # --- Filter ---
        if public_only:
            candidates = [d for d in candidates if d.is_public]
        if owner_id is not None:
            candidates = [d for d in candidates if d.owner_id == owner_id or d.is_public]
        if tags:
            tag_set = {t.lower().strip() for t in tags}
            candidates = [d for d in candidates if tag_set & {t.lower() for t in d.tags}]
        if category:
            candidates = [d for d in candidates if d.category.lower() == category.lower()]
        if platform:
            candidates = [d for d in candidates if d.platform.lower() == platform.lower()]

        # Log non-empty queries for analytics
        if query:
            with self._lock:
                self._query_log.insert(0, query.strip().lower())
                if len(self._query_log) > self._query_log_max:
                    del self._query_log[self._query_log_max:]

        # --- Score ---
        if query:
            query_tokens = _tokenize(query)
            scored = []
            with self._lock:
                # Build prefix expansions for tokens without exact index match
                # Exact match weight = 1.0, prefix match weight = 0.6
                effective_tokens: List[Dict[str, float]] = []
                for qt in query_tokens:
                    if qt in self._inverted:
                        effective_tokens.append({qt: 1.0})
                    else:
                        # Prefix match: find all indexed tokens starting with this token
                        prefix_matches = {
                            tok: 0.6 for tok in self._inverted if tok.startswith(qt) and len(tok) > len(qt)
                        }
                        if prefix_matches:
                            effective_tokens.append(prefix_matches)

                import copy
                for doc in candidates:
                    score = 0.0
                    for tok_weights in effective_tokens:
                        for tok, weight in tok_weights.items():
                            score += self._inverted[tok].get(doc.doc_id, 0) * weight
                    if score > 0:
                        d = copy.copy(doc)
                        d.score = score
                        scored.append(d)
            candidates = scored
        else:
            # No query — return all (score=0)
            for doc in candidates:
                doc.score = 0.0

        # --- Personalization boost (relevance sort only) ---
        if boost_owner_ids and sort_by == "relevance":
            boosted = set(boost_owner_ids)
            import copy as _copy
            boosted_candidates = []
            for d in candidates:
                if d.owner_id in boosted:
                    bd = _copy.copy(d)
                    bd.score = d.score * 1.5 + 0.1
                    boosted_candidates.append(bd)
                else:
                    boosted_candidates.append(d)
            candidates = boosted_candidates

        # --- Sort ---
        if sort_by == "name":
            candidates.sort(key=lambda d: d.name.lower())
        elif sort_by == "newest":
            candidates.sort(key=lambda d: d.created_at, reverse=True)
        elif sort_by == "oldest":
            candidates.sort(key=lambda d: d.created_at)
        else:  # relevance
            candidates.sort(key=lambda d: d.score, reverse=True)

        # --- Facets ---
        facets = self._compute_facets(candidates)

        # --- Paginate ---
        total = len(candidates)
        offset, limit = normalize_pagination(offset, limit)
        page = candidates[offset: offset + limit]
        has_more = offset + limit < total

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "query": query,
            "items": [d.to_dict() for d in page],
            "facets": facets,
        }

    def _compute_facets(self, docs: List[SearchDocument]) -> Dict[str, Any]:
        categories: Dict[str, int] = {}
        platforms: Dict[str, int] = {}
        all_tags: Dict[str, int] = {}
        for doc in docs:
            if doc.category:
                categories[doc.category] = categories.get(doc.category, 0) + 1
            if doc.platform:
                platforms[doc.platform] = platforms.get(doc.platform, 0) + 1
            for tag in doc.tags:
                all_tags[tag] = all_tags.get(tag, 0) + 1
        top_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:20]
        return {
            "categories": categories,
            "platforms": platforms,
            "top_tags": dict(top_tags),
        }

    def suggest(self, prefix: str, limit: int = 10) -> List[str]:
        """Autocomplete suggestions based on index tokens."""
        prefix = prefix.lower()
        with self._lock:
            matches = [tok for tok in self._inverted if tok.startswith(prefix)]
        return sorted(matches, key=lambda t: -len(self._inverted.get(t, {})))[:limit]

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_documents": len(self._docs),
                "total_tokens": len(self._inverted),
            }

    def query_analytics(self, top_n: int = 20) -> Dict[str, Any]:
        """Return top-N most searched queries and total query volume."""
        from collections import Counter
        with self._lock:
            counts = Counter(self._query_log)
            total_queries = len(self._query_log)
        top = [{"query": q, "count": c} for q, c in counts.most_common(top_n)]
        return {
            "total_queries": total_queries,
            "unique_queries": len(counts),
            "top_queries": top,
        }

    # --- Batch indexing ---

    def index_from_dict(self, data: Dict[str, Any]) -> SearchDocument:
        """Build a SearchDocument from an avatar dict and index it."""
        doc = SearchDocument(
            doc_id=data.get("id") or data.get("avatar_id") or data.get("doc_id", ""),
            owner_id=data.get("owner_id") or data.get("user_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            tags=data.get("tags") or [],
            category=data.get("category", ""),
            platform=data.get("platform", ""),
            parameters=data.get("parameters") or {},
            is_public=data.get("is_public", False),
        )
        if "created_at" in data:
            import contextlib
            with contextlib.suppress(ValueError, TypeError):
                doc.created_at = datetime.fromisoformat(data["created_at"])
        self.index(doc)
        return doc


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_search_index: Optional[SearchIndex] = None


def get_search_index() -> SearchIndex:
    global _search_index
    if _search_index is None:
        _search_index = SearchIndex()
    return _search_index
