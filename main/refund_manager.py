"""Refund / return request workflow for Cocoa.

Users may request a refund for a completed order within the refund window.
Admins review, approve, or reject requests.

Rules:
  - Refund window: 72 hours from order creation (configurable via REFUND_WINDOW_HOURS)
  - One pending/approved refund per order (no duplicate requests)
  - Only the order owner can file a refund request
  - Approved refunds: credits returned to buyer; order status → "refunded"
  - Rejection does not restore credits
  - Admins identified by role in auth token payload
"""
from __future__ import annotations

import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

try:
    from .pagination import normalize_pagination
except ImportError:  # pragma: no cover - support flat import in tests
    from pagination import normalize_pagination

logger = logging.getLogger(__name__)

REFUND_WINDOW_HOURS = 72
VALID_STATUSES = frozenset({"pending", "approved", "rejected"})
_MAX_REASON_LEN = 1000
_MAX_NOTES_LEN = 2000


@dataclass
class RefundRequest:
    request_id: str
    order_id: str
    user_id: str
    total_credits: int           # amount to return on approval
    reason: str
    status: str = "pending"      # pending | approved | rejected
    admin_notes: str = ""
    resolved_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "order_id": self.order_id,
            "user_id": self.user_id,
            "total_credits": self.total_credits,
            "reason": self.reason,
            "status": self.status,
            "admin_notes": self.admin_notes,
            "resolved_by": self.resolved_by,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class RefundStore:
    """Thread-safe in-memory refund store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: Dict[str, RefundRequest] = {}         # request_id → RefundRequest
        self._by_order: Dict[str, str] = {}                   # order_id → request_id
        self._user_requests: Dict[str, List[str]] = {}        # user_id → [request_id, ...]

    def create(self, order_id: str, user_id: str, total_credits: int, reason: str) -> RefundRequest:
        with self._lock:
            if order_id in self._by_order:
                existing = self._requests[self._by_order[order_id]]
                if existing.status in ("pending", "approved"):
                    raise ValueError("この注文の払い戻しリクエストはすでに存在します")
            req = RefundRequest(
                request_id=secrets.token_hex(10),
                order_id=order_id,
                user_id=user_id,
                total_credits=total_credits,
                reason=reason.strip()[:_MAX_REASON_LEN],
            )
            self._requests[req.request_id] = req
            self._by_order[order_id] = req.request_id
            self._user_requests.setdefault(user_id, []).append(req.request_id)
            return req

    def get(self, request_id: str) -> Optional[RefundRequest]:
        with self._lock:
            return self._requests.get(request_id)

    def get_by_order(self, order_id: str) -> Optional[RefundRequest]:
        with self._lock:
            rid = self._by_order.get(order_id)
            return self._requests.get(rid) if rid else None

    def list_requests(
        self,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        with self._lock:
            items: List[RefundRequest] = list(self._requests.values())
        if status:
            items = [r for r in items if r.status == status]
        if user_id:
            items = [r for r in items if r.user_id == user_id]
        items.sort(key=lambda r: r.created_at, reverse=True)
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
            "items": [r.to_dict() for r in page],
        }

    def update(self, request_id: str, status: str, notes: str, resolved_by: str) -> RefundRequest:
        with self._lock:
            req = self._requests.get(request_id)
            if not req:
                raise ValueError("払い戻しリクエストが見つかりません")
            req.status = status
            req.admin_notes = notes.strip()[:_MAX_NOTES_LEN]
            req.resolved_by = resolved_by
            req.resolved_at = datetime.now(timezone.utc)
            return req


class RefundManager:
    """Business logic for the refund workflow."""

    def __init__(self, store: Optional[RefundStore] = None) -> None:
        self.store = store or RefundStore()

    # ------------------------------------------------------------------
    # User-facing operations
    # ------------------------------------------------------------------

    def request_refund(
        self,
        user_id: str,
        order_id: str,
        reason: str,
        cart_manager: Any,
    ) -> Dict[str, Any]:
        """File a refund request for a completed order."""
        if not reason or not reason.strip():
            raise ValueError("払い戻し理由を入力してください")

        order = cart_manager.store.get_order(order_id)
        if not order:
            raise ValueError("注文が見つかりません")
        if order.user_id != user_id:
            raise ValueError("この注文に対する払い戻しを申請する権限がありません")
        if order.status != "completed":
            raise ValueError(f"払い戻しできない注文ステータスです: {order.status}")

        cutoff = order.created_at + timedelta(hours=REFUND_WINDOW_HOURS)
        if datetime.now(timezone.utc) > cutoff:
            raise ValueError(
                f"払い戻し期限（{REFUND_WINDOW_HOURS}時間）を過ぎています"
            )

        req = self.store.create(order_id, user_id, order.total_credits, reason)
        logger.info(
            "Refund requested: %s by %s for order %s (%d credits)",
            req.request_id, user_id, order_id, order.total_credits,
        )
        return req.to_dict()

    def get_my_refunds(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        return self.store.list_requests(user_id=user_id, limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # Admin-facing operations
    # ------------------------------------------------------------------

    def _require_admin(self, payload: Dict[str, Any]) -> None:
        role = payload.get("role", "")
        if role not in ("admin", "moderator"):
            raise PermissionError("管理者権限が必要です")

    def approve_refund(
        self,
        admin_payload: Dict[str, Any],
        request_id: str,
        marketplace_store: Any,
        cart_manager: Any,
    ) -> Dict[str, Any]:
        """Approve a refund: claw seller proceeds back, return credits to buyer.

        A paid purchase credits the seller, so a refund must debit the seller
        symmetrically — otherwise credits are minted from nothing and the total
        money supply inflates by the refund amount.  If a seller has already
        spent the proceeds, the clawback is clamped to their available balance
        (the platform absorbs the shortfall) so the buyer's refund is never
        blocked and no balance goes negative.
        """
        self._require_admin(admin_payload)
        req = self.store.get(request_id)
        if not req:
            raise ValueError("払い戻しリクエストが見つかりません")
        if req.status != "pending":
            raise ValueError(f"保留中のリクエストのみ承認できます (現在: {req.status})")

        order = cart_manager.store.get_order(req.order_id)

        # Claw back each seller's proceeds (best-effort, clamped to balance).
        reclaimed = 0
        if order is not None:
            for item in getattr(order, "items", []):
                owed = item.final_price * getattr(item, "quantity", 1)
                if owed <= 0:
                    continue
                available = marketplace_store.get_balance(item.owner_id)
                claw = min(available, owed)
                if claw > 0:
                    marketplace_store.debit(
                        item.owner_id, claw, "sale_reversal", ref_id=req.order_id
                    )
                    reclaimed += claw
                if claw < owed:
                    logger.warning(
                        "Refund clawback shortfall: order=%s seller=%s owed=%d reclaimed=%d",
                        req.order_id, item.owner_id, owed, claw,
                    )

        # Return credits to buyer via the marketplace's audited public API
        new_bal = marketplace_store.credit(
            req.user_id, req.total_credits, "refund", ref_id=req.request_id
        )

        # Mark order refunded
        if order is not None:
            order.status = "refunded"

        admin_id = admin_payload.get("sub", "")
        updated = self.store.update(request_id, "approved", "", admin_id)
        logger.info(
            "Refund approved: %s by admin %s (%d credits → %s, %d reclaimed from sellers)",
            request_id, admin_id, req.total_credits, req.user_id, reclaimed,
        )
        return {
            "request": updated.to_dict(),
            "credits_returned": req.total_credits,
            "new_balance": new_bal,
            "reclaimed_from_sellers": reclaimed,
        }

    def reject_refund(
        self,
        admin_payload: Dict[str, Any],
        request_id: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Reject a refund request (no credits returned)."""
        self._require_admin(admin_payload)
        req = self.store.get(request_id)
        if not req:
            raise ValueError("払い戻しリクエストが見つかりません")
        if req.status != "pending":
            raise ValueError(f"保留中のリクエストのみ却下できます (現在: {req.status})")
        admin_id = admin_payload.get("sub", "")
        updated = self.store.update(request_id, "rejected", notes, admin_id)
        logger.info("Refund rejected: %s by admin %s", request_id, admin_id)
        return updated.to_dict()

    def list_refunds(
        self,
        admin_payload: Dict[str, Any],
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Admin: list all refund requests, optionally filtered by status."""
        self._require_admin(admin_payload)
        if status and status not in VALID_STATUSES:
            raise ValueError(f"不正なステータス: {status}")
        return self.store.list_requests(status=status, limit=limit, offset=offset)

    def get_refund(self, request_id: str) -> Optional[Dict[str, Any]]:
        req = self.store.get(request_id)
        return req.to_dict() if req else None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_refund_manager: Optional[RefundManager] = None
_rm_lock = threading.Lock()


def get_refund_manager() -> RefundManager:
    global _refund_manager
    if _refund_manager is None:
        with _rm_lock:
            if _refund_manager is None:
                _refund_manager = RefundManager()
    return _refund_manager
