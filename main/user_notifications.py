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

try:
    from .pagination import normalize_pagination
except ImportError:  # pragma: no cover - support flat import in tests
    from pagination import normalize_pagination

_MAX_QUEUE = 200        # max stored notifications per user (oldest discarded)
_MAX_TITLE_LEN = 200   # notification title truncation
_MAX_BODY_LEN = 1000   # notification body truncation

# ---------------------------------------------------------------------------
# Notification templates
# ---------------------------------------------------------------------------
NOTIFICATION_TEMPLATES: Dict[str, Dict[str, str]] = {
    "new_follower": {
        "title": "新しいフォロワー",
        "body": "{follower_username} があなたをフォローしました",
    },
    "new_download": {
        "title": "ダウンロード通知",
        "body": "{downloader_username} が「{listing_name}」をダウンロードしました",
    },
    "new_review": {
        "title": "新しいレビュー",
        "body": "{reviewer_username} が「{listing_name}」に {stars}★ のレビューを投稿しました",
    },
    "review_reply": {
        "title": "レビューに返信がありました",
        "body": "{replier_username} があなたのレビューに返信しました",
    },
    "credit_gifted": {
        "title": "クレジットをギフトされました",
        "body": "{sender_username} から {amount} クレジットを受け取りました",
    },
    "listing_published": {
        "title": "アバターが公開されました",
        "body": "「{listing_name}」がマーケットプレイスに公開されました",
    },
    "system_announcement": {
        "title": "お知らせ",
        "body": "{message}",
    },
}

# Notification kinds emitted directly via push() rather than a template
# (services build their own title/body). These are real, user-visible kinds and
# must be mutable just like templated ones.
_DIRECT_PUSH_KINDS = frozenset({
    "price_drop",            # wishlist_manager: wishlisted item dropped in price
    "back_in_stock",         # wishlist_manager: sold-out wishlisted item restocked
    "saved_search_match",    # api_server: a new listing matches a saved search
    "system",                # admin/moderation actions affecting the user
    "commission_received",   # creator: a new commission request arrived
    "commission_response",   # requester: creator accepted/declined
    "commission_delivered",  # requester: commission delivered
    "tip_received",          # a tip was received
})

# The full set of kinds the system can emit. set_muted_kinds() validates against
# this so a user can mute ANY real notification while junk is still rejected
# (an over-narrow allowlist would silently make price_drop/tip/commission
# notifications un-mutable, which is exactly what users want to control).
NOTIFICATION_KINDS = frozenset(NOTIFICATION_TEMPLATES) | _DIRECT_PUSH_KINDS


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
        self._muted: Dict[str, set] = {}  # user_id → set of muted notification kinds
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
    ) -> Optional["UserNotification"]:
        """Push a notification. Returns None (silently dropped) if the kind is muted."""
        with self._lock:
            if kind in self._muted.get(user_id, set()):
                return None
            notif = UserNotification(
                notification_id=self._next_id(),
                user_id=user_id,
                kind=kind,
                title=title[:_MAX_TITLE_LEN],
                body=body[:_MAX_BODY_LEN],
                payload=payload or {},
            )
            q = self._queues.setdefault(user_id, [])
            q.append(notif)
            # Drop oldest if over limit
            if len(q) > self._max:
                del q[: len(q) - self._max]
        return notif

    # --- Notification preferences ---

    def mute_kind(self, user_id: str, kind: str) -> None:
        """Mute a notification kind for a user (future pushes of this kind are silently dropped)."""
        with self._lock:
            self._muted.setdefault(user_id, set()).add(kind)

    def unmute_kind(self, user_id: str, kind: str) -> None:
        """Unmute a notification kind for a user."""
        with self._lock:
            self._muted.get(user_id, set()).discard(kind)

    def get_muted_kinds(self, user_id: str) -> List[str]:
        """Return the list of muted notification kinds for a user."""
        with self._lock:
            return sorted(self._muted.get(user_id, set()))

    def set_muted_kinds(self, user_id: str, kinds: List[str]) -> None:
        """Replace the user's muted-kinds set entirely (only known kinds are accepted)."""
        valid = {k for k in kinds if k in NOTIFICATION_KINDS}
        with self._lock:
            self._muted[user_id] = valid

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
            offset, limit = normalize_pagination(offset, limit)
            page = items[offset: offset + limit]
            unread_count = sum(1 for n in items if not n.is_read)
            serialized = [n.to_dict() for n in page]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "unread_count": unread_count,
            "items": serialized,
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

    def push_from_template(
        self,
        user_id: str,
        template_key: str,
        payload: Optional[Dict[str, Any]] = None,
        **vars: Any,
    ) -> Optional["UserNotification"]:
        """Push a notification rendered from a predefined template."""
        tmpl = NOTIFICATION_TEMPLATES.get(template_key)
        if tmpl is None:
            raise ValueError(f"Unknown notification template: {template_key!r}")
        title = tmpl["title"].format(**vars)
        body = tmpl["body"].format(**vars)
        return self.push(user_id, template_key, title, body, payload)

    def push_batch(
        self,
        user_ids: List[str],
        kind: str,
        title: str,
        body: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Push the same notification to multiple users. Returns number actually delivered (not muted)."""
        count = 0
        for uid in user_ids:
            result = self.push(uid, kind, title, body, payload)
            if result is not None:
                count += 1
        return count

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
_queue_lock = threading.Lock()


def get_notification_queue() -> NotificationQueue:
    global _queue
    if _queue is None:
        with _queue_lock:
            if _queue is None:
                _queue = NotificationQueue()
    return _queue
