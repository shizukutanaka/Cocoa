"""
In-app per-user notification queue for Cocoa platform events.

Stores unread notifications per user_id; the API layer pushes events here
after marketplace / auth operations so no direct module coupling is needed.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_MAX_QUEUE = 200  # max stored notifications per user (oldest discarded)


@dataclass
class UserNotification:
    notification_id: str
    user_id: str
    kind: str          # "new_follower" | "new_download" | "new_review" | "new_listing" | "system"
    title: str
    body: str
    payload: Dict[str, Any] = field(default_factory=dict)
    is_read: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "kind": self.kind,
            "title": self.title,
            "body": self.body,
            "payload": self.payload,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat(),
        }


class NotificationQueue:
    """Thread-safe per-user notification store."""

    def __init__(self, max_per_user: int = _MAX_QUEUE):
        self._queues: Dict[str, List[UserNotification]] = {}
        self._lock = threading.Lock()
        self._max = max_per_user
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"notif-{self._counter:08d}"

    def push(
        self,
        user_id: str,
        kind: str,
        title: str,
        body: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> UserNotification:
        notif = UserNotification(
            notification_id=self._next_id(),
            user_id=user_id,
            kind=kind,
            title=title,
            body=body,
            payload=payload or {},
        )
        with self._lock:
            q = self._queues.setdefault(user_id, [])
            q.append(notif)
            # Drop oldest if over limit
            if len(q) > self._max:
                del q[: len(q) - self._max]
        return notif

    def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        with self._lock:
            items = list(self._queues.get(user_id, []))
        if unread_only:
            items = [n for n in items if not n.is_read]
        items.sort(key=lambda n: n.created_at, reverse=True)
        total = len(items)
        page = items[offset: offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "unread_count": sum(1 for n in items if not n.is_read),
            "items": [n.to_dict() for n in page],
        }

    def mark_read(self, user_id: str, notification_id: str) -> bool:
        with self._lock:
            for notif in self._queues.get(user_id, []):
                if notif.notification_id == notification_id:
                    notif.is_read = True
                    return True
        return False

    def mark_all_read(self, user_id: str) -> int:
        with self._lock:
            count = 0
            for notif in self._queues.get(user_id, []):
                if not notif.is_read:
                    notif.is_read = True
                    count += 1
        return count

    def delete_notification(self, user_id: str, notification_id: str) -> bool:
        with self._lock:
            q = self._queues.get(user_id, [])
            for i, notif in enumerate(q):
                if notif.notification_id == notification_id:
                    del q[i]
                    return True
        return False

    def unread_count(self, user_id: str) -> int:
        with self._lock:
            return sum(1 for n in self._queues.get(user_id, []) if not n.is_read)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total_users = len(self._queues)
            total_notifs = sum(len(q) for q in self._queues.values())
            total_unread = sum(1 for q in self._queues.values() for n in q if not n.is_read)
        return {
            "users_with_notifications": total_users,
            "total_notifications": total_notifs,
            "total_unread": total_unread,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_queue: Optional[NotificationQueue] = None


def get_notification_queue() -> NotificationQueue:
    global _queue
    if _queue is None:
        _queue = NotificationQueue()
    return _queue
