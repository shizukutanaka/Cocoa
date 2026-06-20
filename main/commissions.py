"""
Commission request system

Verified users can send commission requests to creators.
Creators accept or decline; if accepted, they deliver a result
(optionally referencing a marketplace listing). No credit escrow —
payments are handled separately through the marketplace.
"""
from __future__ import annotations

import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from .pagination import normalize_pagination
except ImportError:  # pragma: no cover - support flat import in tests
    from pagination import normalize_pagination

logger = logging.getLogger(__name__)

_MAX_COMMISSIONS_PER_USER = 100  # open commissions per requester
_MAX_DESCRIPTION_LEN = 2000
_MAX_NOTE_LEN = 1000
_MAX_TITLE_LEN = 100

STATUSES = frozenset({"pending", "accepted", "declined", "delivered", "closed"})


@dataclass
class CommissionRequest:
    request_id: str
    requester_id: str
    requester_username: str
    creator_id: str
    title: str
    description: str
    budget_credits: int = 0        # informational; actual payment via marketplace
    status: str = "pending"        # pending | accepted | declined | delivered | closed
    creator_note: str = ""         # creator's acceptance/decline message
    delivery_note: str = ""        # message accompanying delivery
    delivery_listing_id: str = ""  # optional reference to a marketplace listing
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "requester_id": self.requester_id,
            "requester_username": self.requester_username,
            "creator_id": self.creator_id,
            "title": self.title,
            "description": self.description,
            "budget_credits": self.budget_credits,
            "status": self.status,
            "creator_note": self.creator_note,
            "delivery_note": self.delivery_note,
            "delivery_listing_id": self.delivery_listing_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class CommissionStore:
    """Thread-safe in-memory commission request store."""

    def __init__(self):
        self._requests: Dict[str, CommissionRequest] = {}
        self._lock = threading.Lock()

    def create(
        self,
        requester_id: str,
        requester_username: str,
        creator_id: str,
        title: str,
        description: str,
        budget_credits: int = 0,
    ) -> CommissionRequest:
        if requester_id == creator_id:
            raise ValueError("自分自身にコミッションを依頼することはできません")
        title = title.strip()[:_MAX_TITLE_LEN]
        if not title:
            raise ValueError("タイトルを入力してください")
        description = description.strip()[:_MAX_DESCRIPTION_LEN]
        if not description:
            raise ValueError("依頼内容を入力してください")
        if budget_credits < 0:
            raise ValueError("予算は0以上にしてください")
        with self._lock:
            open_count = sum(
                1 for r in self._requests.values()
                if r.requester_id == requester_id and r.status in ("pending", "accepted")
            )
            if open_count >= _MAX_COMMISSIONS_PER_USER:
                raise ValueError(f"オープン中のコミッションが上限 ({_MAX_COMMISSIONS_PER_USER}) に達しています")
            request = CommissionRequest(
                request_id=secrets.token_hex(10),
                requester_id=requester_id,
                requester_username=requester_username,
                creator_id=creator_id,
                title=title,
                description=description,
                budget_credits=budget_credits,
            )
            self._requests[request.request_id] = request
        logger.info("Commission created: %s → creator %s", request.request_id, creator_id)
        return request

    def respond(
        self,
        creator_id: str,
        request_id: str,
        accept: bool,
        note: str = "",
    ) -> CommissionRequest:
        """Creator accepts or declines a pending commission."""
        with self._lock:
            req = self._requests.get(request_id)
            if not req:
                raise ValueError("コミッションが見つかりません")
            if req.creator_id != creator_id:
                raise PermissionError("このコミッションのクリエイターのみが応答できます")
            if req.status != "pending":
                raise ValueError("ペンディング中のコミッションのみ応答できます")
            req.status = "accepted" if accept else "declined"
            req.creator_note = note.strip()[:_MAX_NOTE_LEN]
            req.updated_at = datetime.now(timezone.utc)
        return req

    def deliver(
        self,
        creator_id: str,
        request_id: str,
        delivery_note: str,
        delivery_listing_id: str = "",
    ) -> CommissionRequest:
        """Creator marks a commission as delivered."""
        delivery_note = delivery_note.strip()[:_MAX_NOTE_LEN]
        if not delivery_note:
            raise ValueError("納品メッセージを入力してください")
        with self._lock:
            req = self._requests.get(request_id)
            if not req:
                raise ValueError("コミッションが見つかりません")
            if req.creator_id != creator_id:
                raise PermissionError("このコミッションのクリエイターのみが納品できます")
            if req.status != "accepted":
                raise ValueError("承認済みのコミッションのみ納品できます")
            req.status = "delivered"
            req.delivery_note = delivery_note
            req.delivery_listing_id = delivery_listing_id.strip()[:100]
            req.updated_at = datetime.now(timezone.utc)
        return req

    def close(self, requester_id: str, request_id: str) -> CommissionRequest:
        """Requester closes a commission (after delivery or to cancel pending)."""
        with self._lock:
            req = self._requests.get(request_id)
            if not req:
                raise ValueError("コミッションが見つかりません")
            if req.requester_id != requester_id:
                raise PermissionError("このコミッションの依頼者のみがクローズできます")
            if req.status in ("declined", "closed"):
                raise ValueError("このコミッションはすでに終了しています")
            req.status = "closed"
            req.updated_at = datetime.now(timezone.utc)
        return req

    def get(self, request_id: str) -> Optional[CommissionRequest]:
        with self._lock:
            return self._requests.get(request_id)

    def list_received(
        self,
        creator_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Paginated list of commissions received by a creator."""
        with self._lock:
            items = [r for r in self._requests.values() if r.creator_id == creator_id]
            if status:
                items = [r for r in items if r.status == status]
            items.sort(key=lambda r: r.created_at, reverse=True)
            total = len(items)
            offset, limit = normalize_pagination(offset, limit)
            page = items[offset: offset + limit]
            serialized = [r.to_dict() for r in page]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": serialized,
        }

    def list_sent(
        self,
        requester_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Paginated list of commissions sent by a requester."""
        with self._lock:
            items = [r for r in self._requests.values() if r.requester_id == requester_id]
            if status:
                items = [r for r in items if r.status == status]
            items.sort(key=lambda r: r.created_at, reverse=True)
            total = len(items)
            offset, limit = normalize_pagination(offset, limit)
            page = items[offset: offset + limit]
            serialized = [r.to_dict() for r in page]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": serialized,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_store: Optional[CommissionStore] = None
_store_lock = __import__("threading").Lock()


def get_commission_store() -> CommissionStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = CommissionStore()
    return _store
