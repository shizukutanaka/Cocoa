"""Unified moderation queue for admin content review.

Aggregates all pending moderation items into a single queue:
  - Listing reports (from marketplace)
  - Review reports (from marketplace)
  - Creator applications (from auth_manager)
  - User ban requests (from auth_manager)
  - Commission disputes

Each ModerationItem has:
  - kind: listing_report | review_report | creator_application | user_report
  - source_id: the underlying report/application/etc. ID
  - priority: low | medium | high
  - status: pending | in_review | resolved | dismissed
  - assigned_to: admin user_id or "" if unassigned
  - notes: internal admin notes

This module is a coordination layer — it does not duplicate the underlying
stores but provides a unified view and assignment workflow.
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

VALID_KINDS = frozenset({
    "listing_report",
    "review_report",
    "creator_application",
    "user_report",
    "commission_dispute",
})
VALID_PRIORITIES = frozenset({"low", "medium", "high"})
VALID_STATUSES = frozenset({"pending", "in_review", "resolved", "dismissed"})


@dataclass
class ModerationItem:
    item_id: str
    kind: str               # see VALID_KINDS
    source_id: str          # ID from the underlying system
    subject_id: str         # e.g. listing_id, user_id being reported
    reporter_id: str        # who filed the original complaint
    reason: str
    details: str = ""
    priority: str = "medium"
    status: str = "pending"
    assigned_to: str = ""
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "kind": self.kind,
            "source_id": self.source_id,
            "subject_id": self.subject_id,
            "reporter_id": self.reporter_id,
            "reason": self.reason,
            "details": self.details,
            "priority": self.priority,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class ModerationQueue:
    """Thread-safe moderation queue."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: Dict[str, ModerationItem] = {}
        self._by_source: Dict[str, str] = {}      # source_id → item_id (dedup)

    def enqueue(
        self,
        kind: str,
        source_id: str,
        subject_id: str,
        reporter_id: str,
        reason: str,
        details: str = "",
        priority: str = "medium",
    ) -> ModerationItem:
        """Add an item to the queue. Returns existing item if source_id already queued."""
        if kind not in VALID_KINDS:
            raise ValueError(f"Invalid kind: {kind}. Must be one of {sorted(VALID_KINDS)}")
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {priority}")

        with self._lock:
            if source_id in self._by_source:
                return self._items[self._by_source[source_id]]

            item = ModerationItem(
                item_id=secrets.token_hex(8),
                kind=kind,
                source_id=source_id,
                subject_id=subject_id,
                reporter_id=reporter_id,
                reason=reason,
                details=details[:2000],
                priority=priority,
            )
            self._items[item.item_id] = item
            self._by_source[source_id] = item.item_id
            return item

    def get(self, item_id: str) -> Optional[ModerationItem]:
        with self._lock:
            return self._items.get(item_id)

    def assign(self, item_id: str, admin_id: str) -> ModerationItem:
        with self._lock:
            item = self._items.get(item_id)
            if not item:
                raise ValueError("モデレーションアイテムが見つかりません")
            item.assigned_to = admin_id
            item.status = "in_review"
            item.updated_at = datetime.now(timezone.utc)
            return item

    def update_status(
        self,
        item_id: str,
        status: str,
        notes: str = "",
    ) -> ModerationItem:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        with self._lock:
            item = self._items.get(item_id)
            if not item:
                raise ValueError("モデレーションアイテムが見つかりません")
            item.status = status
            if notes:
                item.notes = notes.strip()[:2000]
            now = datetime.now(timezone.utc)
            item.updated_at = now
            if status in ("resolved", "dismissed"):
                item.resolved_at = now
            return item

    def list_items(
        self,
        status: Optional[str] = None,
        kind: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",  # created_at | priority
    ) -> Dict[str, Any]:
        with self._lock:
            items = list(self._items.values())

        if status:
            items = [i for i in items if i.status == status]
        if kind:
            items = [i for i in items if i.kind == kind]
        if priority:
            items = [i for i in items if i.priority == priority]
        if assigned_to is not None:
            items = [i for i in items if i.assigned_to == assigned_to]

        # Sort
        priority_order = {"high": 0, "medium": 1, "low": 2}
        if sort_by == "priority":
            items.sort(key=lambda i: (priority_order.get(i.priority, 1), i.created_at))
        else:
            items.sort(key=lambda i: i.created_at, reverse=True)

        total = len(items)
        offset, limit = normalize_pagination(offset, limit)
        page = items[offset: offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [i.to_dict() for i in page],
        }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            items = list(self._items.values())
        pending = sum(1 for i in items if i.status == "pending")
        in_review = sum(1 for i in items if i.status == "in_review")
        resolved = sum(1 for i in items if i.status == "resolved")
        dismissed = sum(1 for i in items if i.status == "dismissed")
        by_kind: Dict[str, int] = {}
        by_priority: Dict[str, int] = {}
        for i in items:
            if i.status in ("pending", "in_review"):
                by_kind[i.kind] = by_kind.get(i.kind, 0) + 1
                by_priority[i.priority] = by_priority.get(i.priority, 0) + 1
        return {
            "total": len(items),
            "pending": pending,
            "in_review": in_review,
            "resolved": resolved,
            "dismissed": dismissed,
            "open": pending + in_review,
            "by_kind": by_kind,
            "by_priority": by_priority,
        }

    def set_priority(self, item_id: str, priority: str) -> ModerationItem:
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {priority}")
        with self._lock:
            item = self._items.get(item_id)
            if not item:
                raise ValueError("モデレーションアイテムが見つかりません")
            item.priority = priority
            item.updated_at = datetime.now(timezone.utc)
            return item


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_queue: Optional[ModerationQueue] = None
_q_lock = threading.Lock()


def get_moderation_queue() -> ModerationQueue:
    global _queue
    if _queue is None:
        with _q_lock:
            if _queue is None:
                _queue = ModerationQueue()
    return _queue
