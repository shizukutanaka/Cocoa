"""
Avatar Marketplace

Features:
- Publish avatars as public (share with the community)
- Browse / search public avatars
- Download (clone) a public avatar to your own collection
- Rating system (1-5 stars, one vote per user)
- Tag-based discovery
- Trending / newest / top-rated feeds
"""
from __future__ import annotations

import logging
import os
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from .pagination import normalize_pagination
except ImportError:  # pragma: no cover - support flat import in tests
    from pagination import normalize_pagination

logger = logging.getLogger(__name__)

_MAX_PRICE_CREDITS = int(os.getenv("MAX_PRICE_CREDITS", "10_000_000"))  # 10M cap
_MAX_GRANT_CREDITS = int(os.getenv("MAX_GRANT_CREDITS", "100_000_000"))  # 100M cap per grant


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class ListingVersion:
    version_id: str
    listing_id: str
    version_number: int     # sequential: 1, 2, 3, …
    name: str
    description: str
    parameters: Dict[str, Any]
    changelog: str          # what changed in this version
    created_by: str         # owner_id
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "listing_id": self.listing_id,
            "version_number": self.version_number,
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "changelog": self.changelog,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class MarketplaceListing:
    listing_id: str
    avatar_id: str
    owner_id: str
    owner_username: str
    name: str
    description: str
    tags: List[str]
    category: str
    parameters: Dict[str, Any]
    thumbnail_url: str
    is_free: bool = True
    price_credits: int = 0
    license_type: str = "personal"  # personal | cc_by | cc_by_sa | commercial | custom
    license_details: str = ""
    download_count: int = 0
    rating_sum: int = 0
    rating_count: int = 0
    current_version: int = 1  # latest version number
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    stock_limit: Optional[int] = None      # None = unlimited copies
    stock_remaining: Optional[int] = None  # decremented on each download

    @property
    def average_rating(self) -> float:
        # Read the count ONCE: this property is evaluated outside the store lock
        # (e.g. while search() sorts results), so a concurrent delete_review /
        # rating recompute could flip rating_count from 1→0 between a separate
        # guard-check and divide, raising ZeroDivisionError. One read is safe.
        count = self.rating_count
        if count == 0:
            return 0.0
        return round(self.rating_sum / count, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "avatar_id": self.avatar_id,
            "owner_id": self.owner_id,
            "owner_username": self.owner_username,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "category": self.category,
            "thumbnail_url": self.thumbnail_url,
            "is_free": self.is_free,
            "price_credits": self.price_credits,
            "license_type": self.license_type,
            "license_details": self.license_details,
            "download_count": self.download_count,
            "average_rating": self.average_rating,
            "rating_count": self.rating_count,
            "current_version": self.current_version,
            "published_at": self.published_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "stock_limit": self.stock_limit,
            "stock_remaining": self.stock_remaining,
            "is_sold_out": self.stock_remaining is not None and self.stock_remaining <= 0,
        }


@dataclass
class Review:
    review_id: str
    listing_id: str
    user_id: str
    username: str
    stars: int
    text: str
    helpful_count: int = 0
    unhelpful_count: int = 0
    is_hidden: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "listing_id": self.listing_id,
            "user_id": self.user_id,
            "username": self.username,
            "stars": self.stars,
            "text": self.text,
            "helpful_count": self.helpful_count,
            "unhelpful_count": self.unhelpful_count,
            "is_hidden": self.is_hidden,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class ReviewReply:
    reply_id: str
    review_id: str
    user_id: str
    username: str
    text: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reply_id": self.reply_id,
            "review_id": self.review_id,
            "user_id": self.user_id,
            "username": self.username,
            "text": self.text,
            "created_at": self.created_at.isoformat(),
        }


_REPORT_REASONS = frozenset({
    "inappropriate", "spam", "copyright", "misleading", "malware", "other"
})

_DISPUTE_REASONS = frozenset({
    "not_as_described", "corrupted_file", "duplicate_charge", "unauthorized", "other"
})

# Reserved system account. When the platform absorbs a refund/dispute clawback
# shortfall (a seller already spent the proceeds), the gap is booked here as a
# negative balance so the injection is audited and the economy stays zero-sum.
PLATFORM_ACCOUNT = "__platform__"


@dataclass
class PurchaseDispute:
    dispute_id: str
    listing_id: str
    buyer_id: str
    seller_id: str
    amount_credits: int
    reason: str
    details: str
    status: str = "open"  # open | resolved_refund | resolved_release
    resolved_by: str = ""
    resolution_note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dispute_id": self.dispute_id,
            "listing_id": self.listing_id,
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "amount_credits": self.amount_credits,
            "reason": self.reason,
            "details": self.details,
            "status": self.status,
            "resolved_by": self.resolved_by,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class PromoCode:
    code_id: str
    code: str               # uppercased alphanumeric string
    creator_id: str         # must own the listing (or listing_id=None for any listing by creator)
    discount_percent: int   # 1-99
    listing_id: Optional[str] = None  # None = applies to any of creator's listings
    max_uses: Optional[int] = None    # None = unlimited
    uses_count: int = 0
    expires_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.max_uses is not None and self.uses_count >= self.max_uses:
            return False
        if not self.expires_at:
            return True
        # Defensive: treat a naive expiry as UTC so the comparison can't raise
        # TypeError (mixing naive/aware datetimes) on any record created before
        # expiry normalization was enforced.
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) <= exp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code_id": self.code_id,
            "code": self.code,
            "creator_id": self.creator_id,
            "discount_percent": self.discount_percent,
            "listing_id": self.listing_id,
            "max_uses": self.max_uses,
            "uses_count": self.uses_count,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
            "is_valid": self.is_valid(),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Tip:
    tip_id: str
    sender_id: str
    sender_username: str
    recipient_id: str
    amount: int     # credits transferred
    message: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tip_id": self.tip_id,
            "sender_id": self.sender_id,
            "sender_username": self.sender_username,
            "recipient_id": self.recipient_id,
            "amount": self.amount,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }

    def to_public_dict(self) -> Dict[str, Any]:
        """Public-safe view: sender username + amount only.

        Omits sender_id (stable identifier) and message (private note from the
        sender to the recipient) so a public tips feed cannot leak either.
        """
        return {
            "tip_id": self.tip_id,
            "sender_username": self.sender_username,
            "recipient_id": self.recipient_id,
            "amount": self.amount,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ListingReport:
    report_id: str
    listing_id: str
    reporter_id: str
    reason: str
    details: str
    status: str = "pending"  # pending | resolved | dismissed
    resolved_by: str = ""
    resolution_note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "listing_id": self.listing_id,
            "reporter_id": self.reporter_id,
            "reason": self.reason,
            "details": self.details,
            "status": self.status,
            "resolved_by": self.resolved_by,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class ReviewReport:
    report_id: str
    review_id: str
    reporter_id: str
    reason: str   # spam | offensive | false_info | other
    details: str
    status: str = "pending"  # pending | resolved | dismissed
    resolved_by: str = ""
    resolution_note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "review_id": self.review_id,
            "reporter_id": self.reporter_id,
            "reason": self.reason,
            "details": self.details,
            "status": self.status,
            "resolved_by": self.resolved_by,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


# ---------------------------------------------------------------------------
# In-memory store (production: swap for DB table)
# ---------------------------------------------------------------------------
class MarketplaceStore:
    def __init__(self):
        self._listings: Dict[str, MarketplaceListing] = {}
        self._votes: Dict[str, Dict[str, int]] = {}  # listing_id → {user_id: stars}
        self._reviews: Dict[str, Dict[str, Review]] = {}  # listing_id → {user_id: Review}
        self._download_log: List[Tuple[str, str, datetime, int]] = []  # (listing_id, downloader_id, ts, amount_paid)
        # Ownership index: user_id → set of downloaded listing_ids. Maintained
        # alongside _download_log so "has user X downloaded listing Y?" is O(1)
        # instead of an O(total_downloads) scan of the log on hot paths.
        self._downloads_by_user: Dict[str, Set[str]] = {}
        self._reports: Dict[str, ListingReport] = {}  # report_id → ListingReport
        self._credits: Dict[str, int] = {}  # user_id → credit balance
        self._quotas: Dict[str, int] = {}  # user_id → max active listings (None/missing = unlimited)
        self._review_replies: Dict[str, List[ReviewReply]] = {}  # review_id → [Reply]
        self._review_votes: Dict[str, Dict[str, bool]] = {}  # review_id → {user_id: helpful?}
        self._featured: List[str] = []  # ordered list of featured listing_ids
        self._price_history: Dict[str, List[Dict[str, Any]]] = {}  # listing_id → [{price_credits, is_free, changed_at}]
        self._disputes: Dict[str, PurchaseDispute] = {}  # dispute_id → PurchaseDispute
        self._versions: Dict[str, List[ListingVersion]] = {}  # listing_id → [ListingVersion], oldest first
        self._credit_ledger: Dict[str, List[Dict[str, Any]]] = {}  # user_id → [{amount, kind, ref_id, balance_after, ts}]
        self._review_reports: Dict[str, ReviewReport] = {}  # report_id → ReviewReport
        self._promo_codes: Dict[str, PromoCode] = {}  # code_id → PromoCode
        self._tips: List[Tip] = []  # chronological list of tips
        # Refunded-purchase ledger: (buyer_id, listing_id) pairs that have been
        # refunded through ANY channel (listing dispute OR cart-order refund).
        # Both channels claim a pair here before moving money, so a single
        # purchase can never be refunded twice across the two subsystems.
        self._refunded_purchases: Set[Tuple[str, str]] = set()
        self._lock = threading.Lock()

    # --- Credits ledger ---

    def get_balance(self, user_id: str) -> int:
        with self._lock:
            return self._credits.get(user_id, 0)

    def _append_ledger(
        self,
        user_id: str,
        amount: int,
        kind: str,
        ref_id: str = "",
        balance_after: int = 0,
    ) -> None:
        """Append one credit ledger entry (must be called while holding self._lock)."""
        entry = {
            "amount": amount,
            "kind": kind,
            "ref_id": ref_id,
            "balance_after": balance_after,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self._credit_ledger.setdefault(user_id, []).append(entry)

    # ------------------------------------------------------------------
    # Lock-internal money primitives
    #
    # These are the ONLY place a balance changes.  Every credit-moving path
    # (grants, purchases, sales, gifts, refunds, dispute reversals, and the
    # public credit()/debit() used by other subsystems) routes through them,
    # so a balance change can never happen without a matching ledger entry.
    # Callers MUST already hold self._lock.
    # ------------------------------------------------------------------

    def _credit_locked(self, user_id: str, amount: int, kind: str, ref_id: str = "") -> int:
        """Add ``amount`` (>0) to a balance and record it. Returns new balance."""
        if amount <= 0:
            raise ValueError("amount must be positive")
        new_bal = self._credits.get(user_id, 0) + amount
        self._credits[user_id] = new_bal
        self._append_ledger(user_id, amount, kind, ref_id=ref_id, balance_after=new_bal)
        return new_bal

    def _debit_locked(self, user_id: str, amount: int, kind: str, ref_id: str = "") -> int:
        """Deduct ``amount`` (>0); raise if insufficient. Returns new balance."""
        if amount <= 0:
            raise ValueError("amount must be positive")
        balance = self._credits.get(user_id, 0)
        if balance < amount:
            raise ValueError(f"残高不足 (残高: {balance}, 必要: {amount})")
        new_bal = balance - amount
        self._credits[user_id] = new_bal
        self._append_ledger(user_id, -amount, kind, ref_id=ref_id, balance_after=new_bal)
        return new_bal

    def _subsidize_locked(self, amount: int, ref_id: str = "", kind: str = "platform_subsidy") -> int:
        """Book a platform subsidy: the platform funds ``amount`` (>0), going
        negative on the reserved PLATFORM_ACCOUNT.  Unlike _debit_locked this
        permits a negative balance — the platform account is a deficit ledger,
        not a user wallet.  Records a ledger entry so the injection is audited
        and refunds stay zero-sum across all accounts.  Caller holds self._lock.
        """
        if amount <= 0:
            raise ValueError("amount must be positive")
        new_bal = self._credits.get(PLATFORM_ACCOUNT, 0) - amount
        self._credits[PLATFORM_ACCOUNT] = new_bal
        self._append_ledger(PLATFORM_ACCOUNT, -amount, kind, ref_id=ref_id, balance_after=new_bal)
        return new_bal

    def record_platform_subsidy(self, amount: int, ref_id: str = "", kind: str = "platform_subsidy") -> int:
        """Public, locked wrapper around ``_subsidize_locked``."""
        with self._lock:
            return self._subsidize_locked(amount, ref_id=ref_id, kind=kind)

    # ------------------------------------------------------------------
    # Cross-channel refund guard
    #
    # A cart purchase routes through download() (writing a "purchase" ledger
    # entry + ownership record) AND produces an Order.  That makes it refundable
    # via BOTH the listing-dispute channel and the order-refund channel.  Each
    # channel must claim the (buyer, listing) purchase here before moving money;
    # the second channel sees it already claimed and skips, so one purchase can
    # never be refunded twice.
    # ------------------------------------------------------------------

    def _is_purchase_refunded_locked(self, buyer_id: str, listing_id: str) -> bool:
        """Caller holds self._lock."""
        return (buyer_id, listing_id) in self._refunded_purchases

    def _claim_purchase_refund_locked(self, buyer_id: str, listing_id: str) -> bool:
        """Atomically claim a (buyer, listing) refund. Caller holds self._lock.

        Returns True if newly claimed (caller should proceed to refund),
        False if it was already refunded by another channel (caller must skip).
        """
        key = (buyer_id, listing_id)
        if key in self._refunded_purchases:
            return False
        self._refunded_purchases.add(key)
        return True

    def is_purchase_refunded(self, buyer_id: str, listing_id: str) -> bool:
        with self._lock:
            return self._is_purchase_refunded_locked(buyer_id, listing_id)

    def mark_purchase_refunded(self, buyer_id: str, listing_id: str) -> bool:
        """Public, locked atomic test-and-set used by the order-refund channel.

        Returns True if newly claimed (refund this item), False if it was
        already refunded via a listing dispute (skip it).
        """
        with self._lock:
            return self._claim_purchase_refund_locked(buyer_id, listing_id)

    def _record_download_locked(self, listing_id: str, user_id: str, ts: datetime, amount_paid: int = 0) -> None:
        """Append to the download log AND update the ownership index. Hold lock."""
        self._download_log.append((listing_id, user_id, ts, amount_paid))
        self._downloads_by_user.setdefault(user_id, set()).add(listing_id)

    def _has_downloaded_locked(self, user_id: str, listing_id: str) -> bool:
        """O(1) ownership check. Caller holds self._lock."""
        return listing_id in self._downloads_by_user.get(user_id, ())

    def get_downloaded_ids(self, user_id: str) -> Set[str]:
        """Return a copy of the set of listing_ids the user has downloaded."""
        with self._lock:
            return set(self._downloads_by_user.get(user_id, ()))

    def verify_ledger_integrity(self) -> Dict[str, Any]:
        """Audit invariant: for every user, sum(ledger amounts) == balance.

        The money primitives are the only code that mutates a balance, and each
        records a matching ledger entry, so this should always be consistent.
        A discrepancy therefore means either some code bypassed the primitives
        or restored/persisted state is corrupt — a loud, actionable signal for
        a credit system.  Returns the per-user discrepancies (empty when sound).
        """
        with self._lock:
            discrepancies, users_checked = self._ledger_discrepancies(
                self._credits, self._credit_ledger
            )
        return {
            "consistent": not discrepancies,
            "users_checked": users_checked,
            "discrepancy_count": len(discrepancies),
            "discrepancies": discrepancies,
        }

    @staticmethod
    def _ledger_discrepancies(
        credits: Dict[str, int], ledger: Dict[str, List[Dict[str, Any]]]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Return (discrepancies, users_checked) where balance != sum(ledger)."""
        users = set(credits) | set(ledger)
        discrepancies = []
        for uid in sorted(users):
            balance = credits.get(uid, 0)
            ledger_sum = sum(e["amount"] for e in ledger.get(uid, []))
            if balance != ledger_sum:
                discrepancies.append({
                    "user_id": uid,
                    "balance": balance,
                    "ledger_sum": ledger_sum,
                    "difference": balance - ledger_sum,
                })
        return discrepancies, len(users)

    def export_credit_state(self) -> Dict[str, Any]:
        """Serialize money-critical state (balances + ledger) to a JSON-safe
        dict for durable snapshotting.  Pair with ``import_credit_state``.
        """
        with self._lock:
            return {
                "version": 2,
                "credits": dict(self._credits),
                "ledger": {
                    uid: [dict(e) for e in entries]
                    for uid, entries in self._credit_ledger.items()
                },
                # Cross-channel refund guard: persist so the "one purchase, one
                # refund" guarantee survives a process restart (otherwise a
                # purchase order-refunded before restart could be dispute-refunded
                # after it, minting credits).
                "refunded_purchases": [[b, l] for (b, l) in self._refunded_purchases],
            }

    def import_credit_state(self, state: Dict[str, Any], *, verify: bool = True) -> Dict[str, Any]:
        """Restore balances + ledger from an ``export_credit_state`` snapshot.

        With ``verify=True`` (default) the snapshot is integrity-checked BEFORE
        it is committed — a snapshot whose balances don't match their ledger is
        rejected with ValueError, so corrupt persisted state can never silently
        poison the live credit supply.
        """
        if not isinstance(state, dict) or "credits" not in state:
            raise ValueError("invalid snapshot: missing 'credits'")
        credits = {str(k): int(v) for k, v in state.get("credits", {}).items()}
        ledger = {
            str(k): [dict(e) for e in v]
            for k, v in state.get("ledger", {}).items()
        }
        if verify:
            discrepancies, _ = self._ledger_discrepancies(credits, ledger)
            if discrepancies:
                raise ValueError(
                    f"snapshot integrity check failed: {len(discrepancies)} discrepancies"
                )
        # Restore the cross-channel refund guard if the snapshot carries it
        # (absent in v1 snapshots — left unchanged for backward compatibility).
        refunded = state.get("refunded_purchases")
        with self._lock:
            self._credits = credits
            self._credit_ledger = ledger
            if refunded is not None:
                self._refunded_purchases = {
                    (str(pair[0]), str(pair[1])) for pair in refunded if len(pair) == 2
                }
        return {"users_loaded": len(set(credits) | set(ledger))}

    def save_credit_state(self, path: str) -> None:
        """Atomically persist the money state to a JSON file.

        Writes to a temp file in the same directory and os.replace()s it into
        place, so a crash mid-write can never leave a half-written (corrupt)
        snapshot at ``path`` — the old file stays intact until the new one is
        complete.
        """
        import json
        import tempfile

        state = self.export_credit_state()
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)  # atomic on POSIX
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def load_credit_state(self, path: str, *, verify: bool = True) -> Dict[str, Any]:
        """Load money state from a JSON file written by ``save_credit_state``.

        Returns ``{"loaded": False, "users_loaded": 0}`` if the file does not
        exist (first run), so callers can blindly load on startup.  A corrupt
        snapshot is rejected by the integrity check in ``import_credit_state``.
        """
        import json

        if not os.path.exists(path):
            return {"loaded": False, "users_loaded": 0}
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        result = self.import_credit_state(state, verify=verify)
        result["loaded"] = True
        return result

    def get_credit_history(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        """Return paginated credit transaction history for a user (newest first)."""
        with self._lock:
            all_entries = list(reversed(self._credit_ledger.get(user_id, [])))
        total = len(all_entries)
        offset, limit = normalize_pagination(offset, limit)
        page = all_entries[offset : offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": page,
        }

    def add_credits(self, user_id: str, amount: int) -> int:
        """Add credits to a user's balance (admin grant or purchase). Returns new balance."""
        if amount <= 0:
            raise ValueError("付与額は1以上にしてください")
        if amount > _MAX_GRANT_CREDITS:
            raise ValueError(f"1回の付与上限は {_MAX_GRANT_CREDITS} クレジットです")
        with self._lock:
            return self._credit_locked(user_id, amount, "grant")

    def gift_credits(self, sender_id: str, recipient_id: str, amount: int) -> Dict[str, int]:
        """Transfer credits from sender to recipient. Returns new balances for both."""
        if amount <= 0:
            raise ValueError("ギフト額は1以上の整数で指定してください")
        if sender_id == recipient_id:
            raise ValueError("自分自身にギフトすることはできません")
        with self._lock:
            sender_bal = self._debit_locked(sender_id, amount, "gift_sent", ref_id=recipient_id)
            recipient_bal = self._credit_locked(recipient_id, amount, "gift_received", ref_id=sender_id)
            return {
                "sender_balance": sender_bal,
                "recipient_balance": recipient_bal,
            }

    def credit(self, user_id: str, amount: int, kind: str, ref_id: str = "") -> int:
        """Atomically add credits with a custom ledger kind. Returns new balance.

        Public, audited entry point for other subsystems (gift cards, refunds,
        referrals, …) so they need not touch the private balance store directly.
        """
        with self._lock:
            return self._credit_locked(user_id, amount, kind, ref_id=ref_id)

    def debit(self, user_id: str, amount: int, kind: str, ref_id: str = "") -> int:
        """Atomically deduct credits with a custom ledger kind. Returns new balance.

        Raises ValueError if the balance is insufficient.  Public, audited
        counterpart to ``credit`` for other subsystems.
        """
        with self._lock:
            return self._debit_locked(user_id, amount, kind, ref_id=ref_id)

    # --- Creator quota ---

    def set_quota(self, user_id: str, max_listings: int) -> None:
        """Set max number of active listings for a user (admin only). 0 = blocked."""
        if max_listings < 0:
            raise ValueError("max_listings must be ≥ 0")
        with self._lock:
            self._quotas[user_id] = max_listings

    def get_quota(self, user_id: str) -> Optional[int]:
        """Return the quota for a user, or None if unlimited."""
        with self._lock:
            return self._quotas.get(user_id)

    def get_active_listing_count(self, user_id: str) -> int:
        with self._lock:
            return sum(1 for lst in self._listings.values() if lst.owner_id == user_id and lst.is_active)

    # --- Publish ---

    def publish(
        self,
        avatar_id: str,
        owner_id: str,
        owner_username: str,
        name: str,
        description: str,
        tags: List[str],
        category: str,
        parameters: Dict[str, Any],
        thumbnail_url: str = "",
        is_free: bool = True,
        price_credits: int = 0,
        license_type: str = "personal",
        license_details: str = "",
    ) -> MarketplaceListing:
        # Normalize all string fields once before use so both the listing and the
        # initial version record store the same bounded values.
        name = name.strip()[:200]
        description = description.strip()[:2000]
        category = category.strip()[:50]
        thumbnail_url = thumbnail_url.strip()[:500]
        owner_username = owner_username.strip()[:100]
        license_details = license_details.strip()[:500]
        tags = [t.lower().strip() for t in tags[:20]]
        # Limit parameters payload size: avatar params are shallow key-value dicts;
        # unbounded dicts allow memory/serialization DoS.
        import json as _json
        if price_credits < 0:
            raise ValueError("price_credits must be ≥ 0")
        if price_credits > _MAX_PRICE_CREDITS:
            raise ValueError(f"price_credits must be ≤ {_MAX_PRICE_CREDITS}")
        if len(parameters) > 500:
            raise ValueError("parametersのキー数は500以下にしてください")
        try:
            _param_json = _json.dumps(parameters, ensure_ascii=False)
        except (TypeError, ValueError) as _e:
            raise ValueError(f"parametersをJSONにシリアライズできません: {_e}") from _e
        if len(_param_json) > 65536:
            raise ValueError("parametersのサイズは64KB以下にしてください")

        with self._lock:
            # Enforce creator quota
            quota = self._quotas.get(owner_id)
            if quota is not None:
                active_count = sum(1 for lst in self._listings.values() if lst.owner_id == owner_id and lst.is_active)
                if active_count >= quota:
                    raise ValueError(f"公開上限 ({quota} 件) に達しています。既存のリスティングを削除してから再試行してください")
            # Prevent duplicate listings for same avatar
            for existing in self._listings.values():
                if existing.avatar_id == avatar_id and existing.owner_id == owner_id and existing.is_active:
                    raise ValueError(f"Avatar {avatar_id} is already listed in the marketplace")

            listing = MarketplaceListing(
                listing_id=secrets.token_hex(12),
                avatar_id=avatar_id,
                owner_id=owner_id,
                owner_username=owner_username,
                name=name,
                description=description,
                tags=tags,
                category=category,
                parameters=parameters,
                thumbnail_url=thumbnail_url,
                is_free=is_free,
                price_credits=price_credits,
                license_type=license_type,
                license_details=license_details,
            )
            self._listings[listing.listing_id] = listing
            self._votes[listing.listing_id] = {}
            self._reviews[listing.listing_id] = {}
            # Record initial price
            self._price_history[listing.listing_id] = [{
                "price_credits": price_credits,
                "is_free": is_free,
                "changed_at": listing.published_at.isoformat(),
            }]
            # Record initial version (v1)
            v1 = ListingVersion(
                version_id=secrets.token_hex(8),
                listing_id=listing.listing_id,
                version_number=1,
                name=name,
                description=description,
                parameters=dict(parameters),
                changelog="初回公開",
                created_by=owner_id,
                created_at=listing.published_at,
            )
            self._versions[listing.listing_id] = [v1]
            logger.info("Marketplace listing created: %s by %s", name, owner_username)
            return listing

    # --- Update listing ---

    def update_listing(
        self,
        listing_id: str,
        requester_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        thumbnail_url: Optional[str] = None,
        is_free: Optional[bool] = None,
        price_credits: Optional[int] = None,
        license_type: Optional[str] = None,
        license_details: Optional[str] = None,
    ) -> "MarketplaceListing":
        """Update a published listing. Only the owner may update it."""
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_active:
                raise ValueError("Listing not found or inactive")
            if listing.owner_id != requester_id:
                raise PermissionError("Only the owner can update a listing")
            if name is not None:
                listing.name = name.strip()[:200]
            if description is not None:
                listing.description = description.strip()[:2000]
            if tags is not None:
                listing.tags = [t.lower().strip() for t in tags[:20]]
            if parameters is not None:
                if len(parameters) > 500:
                    raise ValueError("parameters must have ≤ 500 keys")
                listing.parameters = parameters
            if thumbnail_url is not None:
                listing.thumbnail_url = thumbnail_url.strip()[:500]
            old_is_free = listing.is_free
            if is_free is not None:
                listing.is_free = is_free
            price_changed = False
            if price_credits is not None:
                if price_credits < 0:
                    raise ValueError("price_credits must be ≥ 0")
                if price_credits > _MAX_PRICE_CREDITS:
                    raise ValueError(f"price_credits must be ≤ {_MAX_PRICE_CREDITS}")
                if price_credits != listing.price_credits:
                    price_changed = True
                listing.price_credits = price_credits
            if is_free is not None and is_free != old_is_free:
                price_changed = True
            if license_type is not None:
                listing.license_type = license_type
            if license_details is not None:
                listing.license_details = license_details.strip()[:500]
            listing.updated_at = datetime.now(timezone.utc)
            if price_changed:
                self._price_history.setdefault(listing.listing_id, []).append({
                    "price_credits": listing.price_credits,
                    "is_free": listing.is_free,
                    "changed_at": listing.updated_at.isoformat(),
                })
            return listing

    # --- Unpublish ---

    def unpublish(self, listing_id: str, requester_id: str) -> bool:
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                return False
            if listing.owner_id != requester_id:
                raise PermissionError("Only the owner can unpublish a listing")
            listing.is_active = False
            return True

    def admin_deactivate(self, listing_id: str) -> bool:
        """Force-deactivate a listing regardless of owner (admin/moderator action).

        Returns True if the listing existed and was deactivated, False if not found.
        Idempotent — calling on an already-inactive listing is safe and returns True.
        """
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                return False
            listing.is_active = False
            return True

    # --- Download / Clone ---

    def download(
        self, listing_id: str, downloader_id: str, promo_code: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Increment download counter and return the avatar parameters for cloning.

        Raises ValueError if the listing is not free and the downloader has insufficient credits.
        The owner downloading their own listing is always free.
        If promo_code is given and valid, a discount is applied to the purchase price.
        """
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_active:
                return None
            # Stock enforcement: owner can always re-download their own listing
            if listing.stock_remaining is not None and listing.stock_remaining <= 0 and listing.owner_id != downloader_id:
                raise ValueError("在庫がありません (sold out)")
            paid = not listing.is_free and listing.owner_id != downloader_id

            # Re-download: buyer already owns this listing — let them re-download
            # for free rather than charging a second time.
            if paid and self._has_downloaded_locked(downloader_id, listing_id):
                paid = False

            actual_price = listing.price_credits
            applied_promo: Optional[PromoCode] = None
            if paid and promo_code:
                pc = self._resolve_promo(promo_code.upper().strip(), listing_id, listing.owner_id)
                if pc:
                    discount = max(0, min(99, pc.discount_percent))
                    actual_price = max(0, int(listing.price_credits * (100 - discount) / 100))
                    applied_promo = pc

            if paid and actual_price > 0:
                # Buyer pays, seller is credited — symmetric, both via the
                # single money primitive so neither side can be forgotten.
                self._debit_locked(downloader_id, actual_price, "purchase", ref_id=listing_id)
                self._credit_locked(listing.owner_id, actual_price, "sale", ref_id=listing_id)
                if applied_promo:
                    applied_promo.uses_count += 1
            elif paid and applied_promo:
                # A steep discount rounded the price down to 0 — the money
                # primitives reject non-positive amounts, so move nothing, but
                # still consume a promo use (it WAS applied) so max_uses and
                # analytics stay honest. The download proceeds as effectively free.
                applied_promo.uses_count += 1

            now = datetime.now(timezone.utc)
            is_self = listing.owner_id == downloader_id
            # Only non-owner downloads count toward popularity metrics; owner
            # re-downloads are test/preview operations and must not inflate ranking.
            if not is_self:
                listing.download_count += 1
            listing.updated_at = now
            if listing.stock_remaining is not None and not is_self:
                listing.stock_remaining -= 1
                if listing.stock_remaining <= 0:
                    logger.info("Listing sold out: %s", listing_id)
            if not is_self:
                self._record_download_locked(listing_id, downloader_id, now, actual_price if paid else 0)
            result: Dict[str, Any] = {
                "source_listing_id": listing_id,
                "source_avatar_id": listing.avatar_id,
                "name": f"{listing.name} (copy)",
                "parameters": dict(listing.parameters),
                "tags": list(listing.tags),
                "category": listing.category,
                "thumbnail_url": listing.thumbnail_url,
                # Authoritative amount actually debited on THIS download. Zero for
                # free listings, owner self-downloads, and free re-downloads of an
                # already-owned listing. Callers (membership tier accrual, receipts)
                # must use this rather than inferring from listing.price_credits,
                # which would over-count re-downloads and let users farm tier.
                "amount_paid": actual_price if paid else 0,
            }
            if applied_promo:
                result["promo_applied"] = {
                    "code": applied_promo.code,
                    "discount_percent": applied_promo.discount_percent,
                    "original_price": listing.price_credits,
                    "actual_price": actual_price,
                }
            return result

    # --- Rating ---

    def _visible_votes_locked(self, listing_id: str) -> Dict[str, int]:
        """Votes that count toward PUBLIC rating aggregates: a user's stars are
        included only when they have no review or a visible (non-hidden) one.

        This is the single definition of "what the public sees", shared by the
        headline average, the rating distribution, and analytics, so those views
        can never disagree about a moderator-hidden review. Caller holds the lock.
        """
        votes = self._votes.get(listing_id, {})
        reviews = self._reviews.get(listing_id, {})
        return {
            uid: stars for uid, stars in votes.items()
            if not (uid in reviews and reviews[uid].is_hidden)
        }

    def _recompute_rating_locked(self, listing_id: str) -> None:
        """Rebuild a listing's star aggregate from authoritative per-user votes.

        A user's stars count only when they have no review OR their review is
        visible; a moderator-hidden review withdraws that user's rating
        contribution so the listing's public average reflects only the feedback
        a visitor can actually see. Caller must hold self._lock.
        """
        listing = self._listings.get(listing_id)
        if listing is None:
            return
        visible = self._visible_votes_locked(listing_id)
        listing.rating_sum = sum(visible.values())
        listing.rating_count = len(visible)

    def rate(self, listing_id: str, user_id: str, stars: int) -> float:
        if stars < 1 or stars > 5:
            raise ValueError("Rating must be 1–5")
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_active:
                raise ValueError("Listing not found")
            if listing.owner_id == user_id:
                raise ValueError("You cannot rate your own listing")
            if not self._has_downloaded_locked(user_id, listing_id):
                raise ValueError("購入済みのリスティングのみ評価できます")

            self._votes[listing_id][user_id] = stars
            # Keep an existing text review's star display in sync with the vote
            # so the review card never shows a different rating than the one that
            # is actually counted toward the average.
            existing = self._reviews.get(listing_id, {}).get(user_id)
            if existing is not None and existing.stars != stars:
                existing.stars = stars
                existing.updated_at = datetime.now(timezone.utc)
            self._recompute_rating_locked(listing_id)
            return listing.average_rating

    def review(self, listing_id: str, user_id: str, username: str, stars: int, text: str) -> Tuple[float, Review]:
        """Submit or update a star rating with an optional text review."""
        if stars < 1 or stars > 5:
            raise ValueError("Rating must be 1–5")
        text = text.strip()[:2000]
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_active:
                raise ValueError("Listing not found")
            if listing.owner_id == user_id:
                raise ValueError("You cannot review your own listing")
            if not self._has_downloaded_locked(user_id, listing_id):
                raise ValueError("購入済みのリスティングのみレビューできます")

            self._votes[listing_id][user_id] = stars

            existing = self._reviews[listing_id].get(user_id)
            if existing:
                existing.stars = stars
                existing.text = text
                existing.updated_at = datetime.now(timezone.utc)
                rv = existing
            else:
                rv = Review(
                    review_id=secrets.token_hex(10),
                    listing_id=listing_id,
                    user_id=user_id,
                    username=username,
                    stars=stars,
                    text=text,
                )
                self._reviews[listing_id][user_id] = rv
            # Recompute after the review exists so an updated-but-hidden review
            # stays excluded from the aggregate (editing must not bypass moderation).
            self._recompute_rating_locked(listing_id)
            return listing.average_rating, rv

    def get_reviews(
        self,
        listing_id: str,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "newest",  # newest | helpful | rating_high | rating_low
        include_hidden: bool = False,
    ) -> Dict[str, Any]:
        """Return paginated reviews for a listing."""
        listing = self._listings.get(listing_id)
        if not listing:
            return {"total": 0, "items": []}
        with self._lock:
            items = list(self._reviews[listing_id].values())
        if not include_hidden:
            items = [r for r in items if not r.is_hidden]
        if sort_by == "helpful":
            items.sort(key=lambda r: (r.helpful_count, r.created_at), reverse=True)
        elif sort_by == "rating_high":
            items.sort(key=lambda r: (r.stars, r.created_at), reverse=True)
        elif sort_by == "rating_low":
            items.sort(key=lambda r: r.stars)
        else:  # newest
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

    def delete_review(self, listing_id: str, user_id: str) -> bool:
        """Allow a user to delete their own review and remove their rating contribution."""
        with self._lock:
            rv = self._reviews.get(listing_id, {}).pop(user_id, None)
            if rv is not None:
                self._votes.get(listing_id, {}).pop(user_id, None)
                # The review is gone — drop its helpful-votes and replies too so
                # they don't linger unreachable (and can't haunt a recycled id).
                self._review_votes.pop(rv.review_id, None)
                self._review_replies.pop(rv.review_id, None)
                self._recompute_rating_locked(listing_id)
        return rv is not None

    # --- Review replies ---

    def _find_review(self, review_id: str) -> Optional[Review]:
        """Return the Review object for a given review_id (O(n) scan)."""
        for rv_map in self._reviews.values():
            for rv in rv_map.values():
                if rv.review_id == review_id:
                    return rv
        return None

    def hide_review(self, review_id: str) -> Review:
        """Hide a review from public view (moderator action).

        Hiding also withdraws the review's stars from the listing's aggregate so
        moderation is not merely cosmetic — an abusive rating stops dragging the
        score the moment it's hidden.
        """
        with self._lock:
            rv = self._find_review(review_id)
            if rv is None:
                raise ValueError("レビューが見つかりません")
            if not rv.is_hidden:
                rv.is_hidden = True
                self._recompute_rating_locked(rv.listing_id)
        logger.info("Review hidden: %s", review_id)
        return rv

    def unhide_review(self, review_id: str) -> Review:
        """Restore a previously hidden review and re-admit its rating."""
        with self._lock:
            rv = self._find_review(review_id)
            if rv is None:
                raise ValueError("レビューが見つかりません")
            if rv.is_hidden:
                rv.is_hidden = False
                self._recompute_rating_locked(rv.listing_id)
        return rv

    def add_review_reply(
        self, review_id: str, user_id: str, username: str, text: str
    ) -> ReviewReply:
        text = text.strip()[:1000]
        if not text:
            raise ValueError("返信内容を入力してください")
        with self._lock:
            target = self._find_review(review_id)
            if target is None:
                raise ValueError("レビューが見つかりません")
            if target.is_hidden:
                raise ValueError("非表示のレビューには返信できません")
            current_replies = self._review_replies.get(review_id, [])
            if len(current_replies) >= self._MAX_REPLIES_PER_REVIEW:
                raise ValueError(f"1件のレビューへの返信は最大{self._MAX_REPLIES_PER_REVIEW}件までです")
            reply = ReviewReply(
                reply_id=secrets.token_hex(8),
                review_id=review_id,
                user_id=user_id,
                username=username,
                text=text,
            )
            self._review_replies.setdefault(review_id, []).append(reply)
        return reply

    def get_review_replies(self, review_id: str) -> List[ReviewReply]:
        with self._lock:
            return list(self._review_replies.get(review_id, []))

    def delete_review_reply(self, review_id: str, reply_id: str, requester_id: str) -> bool:
        """Delete a reply if the requester is the reply author."""
        with self._lock:
            replies = self._review_replies.get(review_id, [])
            for i, r in enumerate(replies):
                if r.reply_id == reply_id and r.user_id == requester_id:
                    del replies[i]
                    return True
        return False

    def vote_review_helpful(
        self, review_id: str, user_id: str, helpful: bool
    ) -> Dict[str, Any]:
        """Cast or change a helpfulness vote on a review. Returns updated counts.

        Users cannot vote on their own review. Changing vote is allowed.
        Returns None if review not found.
        """
        with self._lock:
            review = self._find_review(review_id)
            if review is None:
                raise ValueError("レビューが見つかりません")
            if review.is_hidden:
                raise ValueError("非表示のレビューには投票できません")
            if review.user_id == user_id:
                raise ValueError("自分のレビューには投票できません")
            votes = self._review_votes.setdefault(review_id, {})
            previous = votes.get(user_id)
            if previous is not None:
                # Undo previous vote
                if previous:
                    review.helpful_count -= 1
                else:
                    review.unhelpful_count -= 1
            if previous == helpful:
                # Toggling off: remove vote
                del votes[user_id]
            else:
                votes[user_id] = helpful
                if helpful:
                    review.helpful_count += 1
                else:
                    review.unhelpful_count += 1
            return {
                "review_id": review_id,
                "helpful_count": review.helpful_count,
                "unhelpful_count": review.unhelpful_count,
                "user_vote": votes.get(user_id),
            }

    def get_user_listings_page(
        self,
        owner_id: str,
        include_inactive: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Return paginated listings for a creator (newest first)."""
        with self._lock:
            items = [
                lst for lst in self._listings.values()
                if lst.owner_id == owner_id and (include_inactive or lst.is_active)
            ]
        items.sort(key=lambda x: x.published_at, reverse=True)
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
            "items": [lst.to_dict() for lst in page],
        }

    def get_categories(self) -> List[Dict[str, Any]]:
        """Return all categories that have at least one active listing, with counts."""
        from collections import Counter
        with self._lock:
            counts: Counter = Counter(
                lst.category
                for lst in self._listings.values()
                if lst.is_active
            )
        return [
            {"category": cat, "count": cnt}
            for cat, cnt in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        ]

    def get_leaderboard(
        self,
        by: str = "downloads",   # downloads | rating | listings
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return top creators ranked by total downloads, average rating, or listing count."""
        from collections import defaultdict
        with self._lock:
            active = [lst for lst in self._listings.values() if lst.is_active]

        stats: Dict[str, Any] = defaultdict(lambda: {
            "total_downloads": 0,
            "total_rating_sum": 0,
            "total_rating_count": 0,
            "listing_count": 0,
            "owner_id": "",
            "owner_username": "",
        })
        for lst in active:
            s = stats[lst.owner_id]
            s["owner_id"] = lst.owner_id
            s["owner_username"] = lst.owner_username
            s["total_downloads"] += lst.download_count
            s["total_rating_sum"] += lst.rating_sum
            s["total_rating_count"] += lst.rating_count
            s["listing_count"] += 1

        entries = list(stats.values())
        for s in entries:
            rc = s["total_rating_count"]
            s["average_rating"] = round(s["total_rating_sum"] / rc, 2) if rc else 0.0

        if by == "rating":
            entries.sort(key=lambda x: (x["average_rating"], x["total_rating_count"]), reverse=True)
        elif by == "listings":
            entries.sort(key=lambda x: x["listing_count"], reverse=True)
        else:  # downloads
            entries.sort(key=lambda x: x["total_downloads"], reverse=True)

        return [
            {k: v for k, v in e.items() if k not in ("total_rating_sum",)}
            for e in entries[:limit]
        ]

    # --- Queries ---

    def search(
        self,
        query: str = "",
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        sort_by: str = "newest",   # newest | downloads | rating | price_asc | price_desc
        limit: int = 20,
        offset: int = 0,
        is_free: Optional[bool] = None,         # True = free only, False = paid only
        min_price: Optional[int] = None,        # inclusive minimum price_credits
        max_price: Optional[int] = None,        # inclusive maximum price_credits
        license_type: Optional[str] = None,     # filter by license_type exact match
        owner_id: Optional[str] = None,         # filter by owner
        include_facets: bool = False,            # if True, include category/tag/license breakdowns
    ) -> Dict[str, Any]:
        query = query[:200]  # cap before any O(n) allocation
        with self._lock:
            results = [lst for lst in self._listings.values() if lst.is_active]

        if query:
            q = query.lower()
            results = [
                lst for lst in results
                if q in lst.name.lower() or q in lst.description.lower() or q in lst.owner_username.lower()
            ]

        if tags:
            tag_set = {t.lower().strip()[:64] for t in tags[:50]}
            results = [lst for lst in results if tag_set & set(lst.tags)]

        if category:
            results = [lst for lst in results if lst.category.lower() == category.lower()]

        if owner_id:
            results = [lst for lst in results if lst.owner_id == owner_id]

        if license_type:
            results = [lst for lst in results if lst.license_type == license_type]

        # Price filters
        if is_free is not None:
            results = [lst for lst in results if lst.is_free == is_free]
        if min_price is not None:
            results = [lst for lst in results if lst.price_credits >= min_price]
        if max_price is not None:
            results = [lst for lst in results if lst.price_credits <= max_price]

        # Sort
        if sort_by == "downloads":
            results.sort(key=lambda x: x.download_count, reverse=True)
        elif sort_by == "rating":
            results.sort(key=lambda x: (x.average_rating, x.rating_count), reverse=True)
        elif sort_by == "price_asc":
            results.sort(key=lambda x: x.price_credits)
        elif sort_by == "price_desc":
            results.sort(key=lambda x: x.price_credits, reverse=True)
        else:  # newest
            results.sort(key=lambda x: x.published_at, reverse=True)

        total = len(results)
        offset, limit = normalize_pagination(offset, limit)
        page = results[offset: offset + limit]
        has_more = offset + limit < total
        response: Dict[str, Any] = {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [lst.to_dict() for lst in page],
        }
        if include_facets:
            from collections import Counter
            cat_counts: Counter = Counter(lst.category for lst in results)
            lic_counts: Counter = Counter(lst.license_type for lst in results)
            tag_counts: Counter = Counter(
                tag for lst in results for tag in lst.tags
            )
            response["facets"] = {
                "categories": dict(cat_counts.most_common()),
                "license_types": dict(lic_counts.most_common()),
                "top_tags": dict(tag_counts.most_common(20)),
            }
        return response

    def get_listing(self, listing_id: str) -> Optional[MarketplaceListing]:
        return self._listings.get(listing_id)

    def get_user_listings(self, owner_id: str) -> List[MarketplaceListing]:
        return [lst for lst in self._listings.values() if lst.owner_id == owner_id and lst.is_active]

    def deactivate_all_listings(self, owner_id: str) -> List[str]:
        """Force-deactivate every active listing owned by ``owner_id``.

        Called when the owner's account is deleted so orphaned listings don't
        remain purchasable. Returns the ids of the listings that were
        deactivated so the caller can sync external indexes (e.g. search).
        """
        deactivated: List[str] = []
        with self._lock:
            for lst in self._listings.values():
                if lst.owner_id == owner_id and lst.is_active:
                    lst.is_active = False
                    deactivated.append(lst.listing_id)
        if deactivated:
            logger.info("Deactivated %d listings for deleted user %s", len(deactivated), owner_id)
        return deactivated

    def get_trending(self, limit: int = 10, days: int = 7) -> List[Dict[str, Any]]:
        """Top listings by recent downloads (within `days` days), falling back to all-time if none."""
        from collections import Counter
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with self._lock:
            recent_counts: Counter = Counter(
                lid for lid, _, ts, _ap in self._download_log if ts >= cutoff
            )
            active = [lst for lst in self._listings.values() if lst.is_active]
        if recent_counts:
            active.sort(key=lambda x: recent_counts.get(x.listing_id, 0), reverse=True)
        else:
            active.sort(key=lambda x: x.download_count, reverse=True)
        return [lst.to_dict() for lst in active[:limit]]

    def get_trending_tags(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Aggregate tag popularity across active listings, weighted by downloads.

        Each tag's score = (# listings using it) + (total downloads of those listings).
        Returns [{tag, listing_count, download_count, score}, ...] descending by score.
        """
        from collections import defaultdict
        with self._lock:
            active = [lst for lst in self._listings.values() if lst.is_active]
        listing_counts: Dict[str, int] = defaultdict(int)
        download_counts: Dict[str, int] = defaultdict(int)
        for lst in active:
            for tag in lst.tags:
                listing_counts[tag] += 1
                download_counts[tag] += lst.download_count
        rows = [
            {
                "tag": tag,
                "listing_count": listing_counts[tag],
                "download_count": download_counts[tag],
                "score": listing_counts[tag] + download_counts[tag],
            }
            for tag in listing_counts
        ]
        rows.sort(key=lambda r: (r["score"], r["listing_count"]), reverse=True)
        return rows[:limit]

    def get_tag_feed(
        self,
        tags: List[str],
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "newest",
    ) -> Dict[str, Any]:
        """Return active listings matching ANY of the given tags, paginated."""
        tag_set = {t.lower().strip() for t in tags if t.strip()}
        if not tag_set:
            return {"total": 0, "offset": offset, "limit": limit,
                    "has_more": False, "next_offset": None, "items": []}
        with self._lock:
            results = [
                lst for lst in self._listings.values()
                if lst.is_active and any(t in tag_set for t in lst.tags)
            ]
        if sort_by == "downloads":
            results.sort(key=lambda x: x.download_count, reverse=True)
        elif sort_by == "rating":
            results.sort(key=lambda x: x.average_rating, reverse=True)
        else:  # newest
            results.sort(key=lambda x: x.published_at, reverse=True)
        total = len(results)
        offset, limit = normalize_pagination(offset, limit)
        page = results[offset: offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [lst.to_dict() for lst in page],
        }

    # --- Featured listings (admin-curated) ---

    def feature_listing(self, listing_id: str) -> bool:
        """Add a listing to the featured list (no-op if already featured)."""
        with self._lock:
            if listing_id in self._listings and listing_id not in self._featured:
                self._featured.append(listing_id)
                return True
        return False

    def unfeature_listing(self, listing_id: str) -> bool:
        """Remove a listing from the featured list."""
        with self._lock:
            try:
                self._featured.remove(listing_id)
                return True
            except ValueError:
                return False

    def get_featured(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return featured active listings in curator order."""
        with self._lock:
            ids = list(self._featured[:limit])
        result = []
        for lid in ids:
            lst = self._listings.get(lid)
            if lst and lst.is_active:
                result.append(lst.to_dict())
        return result

    # --- Price history ---

    def get_price_history(self, listing_id: str) -> List[Dict[str, Any]]:
        """Return the price change log for a listing (oldest first)."""
        with self._lock:
            return list(self._price_history.get(listing_id, []))

    # --- Listing versions ---

    def publish_version(
        self,
        listing_id: str,
        requester_id: str,
        changelog: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> ListingVersion:
        """Create a new version of an existing listing. Only the owner can do this."""
        changelog = changelog.strip()[:1000]
        if not changelog:
            raise ValueError("変更履歴を入力してください")
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_active:
                raise ValueError("リスティングが見つかりません")
            if listing.owner_id != requester_id:
                raise PermissionError("オーナーのみバージョンを更新できます")
            # Update listing fields if provided
            if name is not None:
                listing.name = name.strip()[:200]
            if description is not None:
                listing.description = description.strip()[:2000]
            if parameters is not None:
                listing.parameters = parameters
            listing.current_version += 1
            listing.updated_at = datetime.now(timezone.utc)
            version = ListingVersion(
                version_id=secrets.token_hex(8),
                listing_id=listing_id,
                version_number=listing.current_version,
                name=listing.name,
                description=listing.description,
                parameters=dict(listing.parameters),
                changelog=changelog,
                created_by=requester_id,
            )
            self._versions.setdefault(listing_id, []).append(version)
        logger.info("Version %d published for listing %s", listing.current_version, listing_id)
        return version

    def get_versions(self, listing_id: str) -> List[ListingVersion]:
        """Return all versions for a listing (oldest first)."""
        with self._lock:
            return list(self._versions.get(listing_id, []))

    def get_version(self, listing_id: str, version_number: int) -> Optional[ListingVersion]:
        with self._lock:
            for v in self._versions.get(listing_id, []):
                if v.version_number == version_number:
                    return v
        return None

    # --- Purchase disputes ---

    def open_dispute(
        self,
        listing_id: str,
        buyer_id: str,
        reason: str,
        details: str = "",
    ) -> PurchaseDispute:
        if reason not in _DISPUTE_REASONS:
            raise ValueError(f"Invalid reason. Must be one of: {', '.join(sorted(_DISPUTE_REASONS))}")
        details = details.strip()[:1000]
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                raise ValueError("リスティングが見つかりません")
            if listing.is_free or listing.price_credits == 0:
                raise ValueError("無料リスティングは争議の対象外です")
            # Verify buyer actually downloaded this listing (O(1) via index)
            if not self._has_downloaded_locked(buyer_id, listing_id):
                raise ValueError("ダウンロード履歴がありません")
            # One dispute per buyer/listing pair, regardless of status.
            # A resolved dispute (refund or release) cannot be re-opened, and
            # a dismissed dispute cannot be filed again — one chance per purchase.
            for d in self._disputes.values():
                if d.listing_id == listing_id and d.buyer_id == buyer_id:
                    raise ValueError("この購入に対する争議は既に存在します")
            # Dispute the amount the buyer ACTUALLY paid (the most recent
            # purchase ledger entry for this listing), not the list price —
            # a promo/bundle discount means they paid less, and refunding the
            # full price would over-compensate the buyer and over-charge the
            # seller on clawback.  Fall back to the list price if no purchase
            # entry is found.
            paid = listing.price_credits
            for entry in reversed(self._credit_ledger.get(buyer_id, [])):
                if entry.get("kind") == "purchase" and entry.get("ref_id") == listing_id:
                    paid = -entry["amount"]
                    break
            dispute = PurchaseDispute(
                dispute_id=secrets.token_hex(8),
                listing_id=listing_id,
                buyer_id=buyer_id,
                seller_id=listing.owner_id,
                amount_credits=paid,
                reason=reason,
                details=details,
            )
            self._disputes[dispute.dispute_id] = dispute
        logger.info("Dispute opened: %s by buyer %s on listing %s", dispute.dispute_id, buyer_id, listing_id)
        return dispute

    def resolve_dispute(
        self,
        dispute_id: str,
        admin_id: str,
        decision: str,  # "refund" | "release"
        note: str = "",
    ) -> PurchaseDispute:
        if decision not in ("refund", "release"):
            raise ValueError("decision must be 'refund' or 'release'")
        with self._lock:
            dispute = self._disputes.get(dispute_id)
            if not dispute:
                raise ValueError("争議が見つかりません")
            if dispute.status != "open":
                raise ValueError("この争議はすでに解決されています")
            # Block a refund if this purchase was already refunded via the
            # order-refund channel — checked BEFORE mutating dispute state so the
            # dispute stays "open" and a release (or manual handling) is possible.
            if decision == "refund" and self._is_purchase_refunded_locked(
                dispute.buyer_id, dispute.listing_id
            ):
                raise ValueError("この購入はすでに払い戻し済みです")
            dispute.status = f"resolved_{decision}"
            dispute.resolved_by = admin_id
            dispute.resolution_note = note.strip()[:500]
            dispute.resolved_at = datetime.now(timezone.utc)
            if decision == "refund":
                # Claim the purchase so the order-refund channel can't also
                # refund it (zero-sum guarantee across both subsystems).
                self._claim_purchase_refund_locked(dispute.buyer_id, dispute.listing_id)
                # Refund the buyer AND claw the proceeds back from the seller so
                # the dispute does not mint credits, recording both sides in the
                # ledger.  The clawback is clamped to the seller's balance (the
                # platform absorbs any shortfall) to keep balances non-negative.
                amount = dispute.amount_credits
                self._credit_locked(dispute.buyer_id, amount, "dispute_refund",
                                    ref_id=dispute.listing_id)
                seller_avail = self._credits.get(dispute.seller_id, 0)
                claw = min(seller_avail, amount)
                if claw > 0:
                    self._debit_locked(dispute.seller_id, claw, "dispute_reversal",
                                       ref_id=dispute.listing_id)
                if claw < amount:
                    # Platform funds the gap; book it so the refund is zero-sum
                    # across all accounts and the injection is audited.
                    self._subsidize_locked(amount - claw, ref_id=dispute.listing_id,
                                           kind="dispute_subsidy")
                    logger.warning(
                        "Dispute clawback shortfall: dispute=%s seller=%s owed=%d clawed=%d",
                        dispute_id, dispute.seller_id, amount, claw,
                    )
        logger.info("Dispute %s resolved: %s by admin %s", dispute_id, decision, admin_id)
        return dispute

    def get_disputes(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        with self._lock:
            items = list(self._disputes.values())
        if status:
            items = [d for d in items if d.status == status]
        items.sort(key=lambda d: d.created_at, reverse=True)
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
            "items": [d.to_dict() for d in page],
        }

    def get_related(self, listing_id: str, limit: int = 6) -> List[Dict[str, Any]]:
        """Return listings similar to the given one, scored by shared tags + same category.

        Scoring: +2 per shared tag, +1 for same category. Excludes the source listing.
        """
        with self._lock:
            source = self._listings.get(listing_id)
            if not source:
                return []
            candidates = [lst for lst in self._listings.values() if lst.is_active and lst.listing_id != listing_id]

        src_tags = set(source.tags)
        src_cat = source.category.lower()
        scored: List[Tuple[float, "MarketplaceListing"]] = []
        for lst in candidates:
            score = 2 * len(src_tags & set(lst.tags))
            if lst.category.lower() == src_cat:
                score += 1
            if score > 0:
                scored.append((score, lst))
        scored.sort(key=lambda x: (-x[0], -x[1].download_count))
        return [lst.to_dict() for _, lst in scored[:limit]]

    def has_downloaded(self, listing_id: str, user_id: str) -> bool:
        """Return True if user_id has downloaded listing_id (O(1) via index)."""
        with self._lock:
            return self._has_downloaded_locked(user_id, listing_id)

    def get_rating_distribution(self, listing_id: str) -> Dict[str, Any]:
        """Return per-star vote counts and average for a listing.

        Counts only votes visible to the public (hidden-review votes excluded)
        so this average matches the listing's headline average_rating exactly.
        """
        with self._lock:
            votes = self._visible_votes_locked(listing_id)
        dist: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for stars in votes.values():
            if 1 <= stars <= 5:
                dist[stars] += 1
        total = sum(dist.values())
        avg = round(sum(k * v for k, v in dist.items()) / total, 2) if total else 0.0
        return {
            "listing_id": listing_id,
            "distribution": dist,
            "total_ratings": total,
            "average_rating": avg,
        }

    def clone_listing(
        self, listing_id: str, requester_id: str, requester_username: str
    ) -> "MarketplaceListing":
        """Clone a listing as a new published listing owned by requester.

        Copies all metadata but resets download/rating counters and sets a new owner.
        Useful for remixing a free/open-source avatar.
        """
        with self._lock:
            source = self._listings.get(listing_id)
            if not source or not source.is_active:
                raise ValueError("リスティングが見つかりません")
            if source.license_type not in ("cc_by", "cc_by_sa"):
                raise PermissionError("このライセンスではクローンできません（CC BY または CC BY-SA のみ）")
        # publish uses the lock internally — call outside to avoid deadlock
        cloned = self.publish(
            avatar_id=secrets.token_hex(8),
            owner_id=requester_id,
            owner_username=requester_username,
            name=f"{source.name} (clone)",
            description=source.description,
            tags=list(source.tags),
            category=source.category,
            parameters=dict(source.parameters),
            thumbnail_url=source.thumbnail_url,
            is_free=True,  # clones are always free
            price_credits=0,
            license_type=source.license_type,
            license_details=f"Cloned from listing {listing_id}. {source.license_details}".strip(),
        )
        return cloned

    def transfer_listing(
        self,
        listing_id: str,
        requester_id: str,
        new_owner_id: str,
        new_owner_username: str,
    ) -> "MarketplaceListing":
        """Transfer ownership of a listing to another user.

        Only the current owner may initiate a transfer.
        The listing remains active; all reviews/ratings/downloads are preserved.
        """
        if requester_id == new_owner_id:
            raise ValueError("自分自身に譲渡することはできません")
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                raise ValueError("リスティングが見つかりません")
            if listing.owner_id != requester_id:
                raise PermissionError("このリスティングの所有者のみが譲渡できます")
            listing.owner_id = new_owner_id
            listing.owner_username = new_owner_username
        logger.info("Listing %s transferred from %s to %s", listing_id, requester_id, new_owner_id)
        return listing

    def set_stock_limit(
        self, listing_id: str, owner_id: str, stock_limit: Optional[int]
    ) -> "MarketplaceListing":
        """Set or clear a stock limit for a listing.

        Pass stock_limit=None to make the listing unlimited again.
        Pass a positive integer to cap the number of copies sold.
        Only the listing owner may call this.
        """
        if stock_limit is not None and stock_limit < 0:
            raise ValueError("在庫数は0以上の値を指定してください")
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                raise ValueError("リスティングが見つかりません")
            if listing.owner_id != owner_id:
                raise PermissionError("このリスティングの所有者のみが在庫を設定できます")
            if stock_limit is None:
                listing.stock_limit = None
                listing.stock_remaining = None
            else:
                already_sold = listing.download_count
                remaining = max(0, stock_limit - already_sold)
                listing.stock_limit = stock_limit
                listing.stock_remaining = remaining
            listing.updated_at = datetime.now(timezone.utc)
        logger.info("Stock limit set for listing %s: %s", listing_id, stock_limit)
        return listing

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            active = [lst for lst in self._listings.values() if lst.is_active]
        return {
            "total_listings": len(active),
            "total_downloads": sum(lst.download_count for lst in active),
            "total_ratings": sum(lst.rating_count for lst in active),
            "categories": list({lst.category for lst in active}),
        }

    def get_listing_analytics(self, listing_id: str, owner_id: str) -> Dict[str, Any]:
        """Download/rating analytics for a single listing.

        Only the listing owner may call this (pass owner_id for enforcement).
        Returns download counts by day, reviewer count, and rating breakdown.
        """
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                raise ValueError("リスティングが見つかりません")
            if listing.owner_id != owner_id:
                raise PermissionError("このリスティングの所有者のみが分析情報を取得できます")
            logs = [(lid, did, ts) for lid, did, ts, _ap in self._download_log if lid == listing_id]
            review_count = len(self._reviews.get(listing_id, {}))
            # Snapshot visible votes under the lock (was read unlocked before,
            # and counted hidden-review votes the headline average excludes).
            visible_votes = list(self._visible_votes_locked(listing_id).values())

        from collections import Counter
        day_counts: Counter = Counter()
        unique_downloaders: set = set()
        for _, did, ts in logs:
            day_counts[ts.strftime("%Y-%m-%d")] += 1
            unique_downloaders.add(did)

        dist: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for stars in visible_votes:
            if 1 <= stars <= 5:
                dist[stars] += 1
        rating_total = sum(dist.values())
        avg = round(sum(k * v for k, v in dist.items()) / rating_total, 2) if rating_total else 0.0

        return {
            "listing_id": listing_id,
            "name": listing.name,
            "total_downloads": listing.download_count,
            "unique_downloaders": len(unique_downloaders),
            "total_reviews": review_count,
            "average_rating": avg,
            "rating_distribution": dist,
            "downloads_by_day": dict(day_counts),
        }

    def get_creator_analytics(self, owner_id: str) -> Dict[str, Any]:
        """Per-creator dashboard stats."""
        with self._lock:
            listings = [lst for lst in self._listings.values() if lst.owner_id == owner_id]
            logs = [(lid, did, ts, ap) for lid, did, ts, ap in self._download_log
                    if self._listings.get(lid) and self._listings[lid].owner_id == owner_id]
            # Snapshot review/vote counts under the lock so we're consistent with listings.
            listing_ids = {lst.listing_id for lst in listings}
            review_counts = {lid: len(self._reviews.get(lid, {})) for lid in listing_ids}
            # Visible votes only, so the distribution matches each listing's
            # headline average (hidden-review votes excluded).
            vote_snapshots = {lid: self._visible_votes_locked(lid) for lid in listing_ids}

        total_downloads = sum(lst.download_count for lst in listings)
        active_count = sum(1 for lst in listings if lst.is_active)
        total_reviews = sum(review_counts.values())

        # Rating distribution across all listings
        rating_dist: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for lid, stars_by_user in vote_snapshots.items():
            for stars in stars_by_user.values():
                rating_dist[stars] = rating_dist.get(stars, 0) + 1

        # Downloads by day (last 30 days)
        from collections import Counter
        day_counts: Counter = Counter()
        for _, _, ts, _ap in logs:
            day_counts[ts.strftime("%Y-%m-%d")] += 1

        # Downloads by tag and category
        listing_map = {lst.listing_id: lst for lst in listings}
        tag_counts: Counter = Counter()
        category_counts: Counter = Counter()
        for lid, _, _, _ap in logs:
            lst = listing_map.get(lid)
            if lst:
                for tag in lst.tags:
                    tag_counts[tag] += 1
                if lst.category:
                    category_counts[lst.category] += 1

        # Revenue: sum the amount_paid stored at download time so re-downloads
        # (charged 0) and promo discounts are reflected accurately, not inflated
        # by the listing's current price.
        credits_earned = sum(ap for _, _, _, ap in logs)

        # Top listing by downloads
        top = max(listings, key=lambda lst: lst.download_count, default=None)

        return {
            "owner_id": owner_id,
            "total_listings": len(listings),
            "active_listings": active_count,
            "total_downloads": total_downloads,
            "total_reviews": total_reviews,
            "total_credits_earned": credits_earned,
            "rating_distribution": rating_dist,
            "downloads_by_day": dict(day_counts),
            "downloads_by_tag": dict(tag_counts.most_common(20)),
            "downloads_by_category": dict(category_counts),
            "top_listing": top.to_dict() if top else None,
        }

    # --- Earnings summary ---

    def get_earnings_summary(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Aggregate credit earnings from sales and tips for the given window.

        Returns totals by source (sales, tips_received, gifts_received) and a
        day-by-day breakdown for charting.  Uses the credit ledger as the source
        of truth so amounts are always consistent with actual credit movements.
        """
        from collections import defaultdict
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400

        with self._lock:
            entries = list(self._credit_ledger.get(user_id, []))

        total_sales = 0
        total_tips = 0
        by_day: Dict[str, int] = defaultdict(int)

        for entry in entries:
            amount = entry["amount"]
            kind = entry["kind"]
            ts_str = entry.get("ts", "")
            try:
                ts = datetime.fromisoformat(ts_str)
            except (ValueError, TypeError):
                continue
            if ts.timestamp() < cutoff:
                continue

            day = ts.strftime("%Y-%m-%d")
            if kind == "sale" and amount > 0:
                total_sales += amount
                by_day[day] += amount
            elif kind in ("tip_received", "gift_received") and amount > 0:
                total_tips += amount
                by_day[day] += amount

        return {
            "user_id": user_id,
            "period_days": days,
            "total_earned": total_sales + total_tips,
            "sales": total_sales,
            "tips_and_gifts_received": total_tips,
            "by_day": dict(sorted(by_day.items())),
        }

    # --- Download history ---

    def get_user_download_history(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Return paginated list of listings this user has downloaded, newest first."""
        with self._lock:
            entries = [(lid, ts) for lid, did, ts, _ap in self._download_log if did == user_id]
        entries.sort(key=lambda x: x[1], reverse=True)
        total = len(entries)
        offset, limit = normalize_pagination(offset, limit)
        page = entries[offset: offset + limit]
        items = []
        for lid, ts in page:
            listing = self._listings.get(lid)
            row: Dict[str, Any] = {"listing_id": lid, "downloaded_at": ts.isoformat()}
            if listing:
                row["name"] = listing.name
                row["owner_username"] = listing.owner_username
                row["is_active"] = listing.is_active
            items.append(row)
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": items,
        }

    # --- Moderation / reports ---

    def report_listing(self, listing_id: str, reporter_id: str, reason: str, details: str = "") -> ListingReport:
        """File a moderation report against a listing."""
        if reason not in _REPORT_REASONS:
            raise ValueError(f"Invalid reason. Must be one of: {', '.join(sorted(_REPORT_REASONS))}")
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                raise ValueError("Listing not found")
            if listing.owner_id == reporter_id:
                raise ValueError("自分のリスティングを報告することはできません")
            # Prevent duplicate pending reports from same reporter
            for existing in self._reports.values():
                if (existing.listing_id == listing_id and existing.reporter_id == reporter_id
                        and existing.status == "pending"):
                    raise ValueError("You already have a pending report for this listing")
            report = ListingReport(
                report_id=secrets.token_hex(10),
                listing_id=listing_id,
                reporter_id=reporter_id,
                reason=reason,
                details=details.strip()[:1000],
            )
            self._reports[report.report_id] = report
            logger.info("Listing reported: %s (reason=%s)", listing_id, reason)
            return report

    def get_reports(self, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List moderation reports, optionally filtered by status (admin)."""
        with self._lock:
            items = list(self._reports.values())
        if status:
            items = [r for r in items if r.status == status]
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

    def resolve_report(self, report_id: str, moderator_id: str, action: str, note: str = "", *, takedown: bool = False) -> ListingReport:
        """Resolve a report. action: 'resolved' | 'dismissed'. If takedown, unpublish the listing."""
        if action not in ("resolved", "dismissed"):
            raise ValueError("action must be 'resolved' or 'dismissed'")
        with self._lock:
            report = self._reports.get(report_id)
            if not report:
                raise ValueError("Report not found")
            if report.status != "pending":
                raise ValueError("このレポートはすでに処理済みです")
            report.status = action
            report.resolved_by = moderator_id
            report.resolution_note = note.strip()[:1000]
            report.resolved_at = datetime.now(timezone.utc)
            if takedown:
                listing = self._listings.get(report.listing_id)
                if listing:
                    listing.is_active = False
                    logger.info("Listing taken down via moderation: %s", report.listing_id)
            return report

    def get_report_stats(self) -> Dict[str, Any]:
        with self._lock:
            items = list(self._reports.values())
        by_status: Dict[str, int] = {"pending": 0, "resolved": 0, "dismissed": 0}
        by_reason: Dict[str, int] = {}
        for r in items:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            by_reason[r.reason] = by_reason.get(r.reason, 0) + 1
        return {"total": len(items), "by_status": by_status, "by_reason": by_reason}

    # --- Review reports ---

    _REVIEW_REPORT_REASONS = frozenset({"spam", "offensive", "false_info", "other"})

    def report_review(
        self, review_id: str, reporter_id: str, reason: str, details: str = ""
    ) -> ReviewReport:
        """File a report against a review. One pending report per user per review."""
        if reason not in self._REVIEW_REPORT_REASONS:
            raise ValueError(f"reason は {sorted(self._REVIEW_REPORT_REASONS)} のいずれかです")
        with self._lock:
            if self._find_review(review_id) is None:
                raise ValueError("レビューが見つかりません")
            for existing in self._review_reports.values():
                if existing.review_id == review_id and existing.reporter_id == reporter_id and existing.status == "pending":
                    raise ValueError("すでにこのレビューへの報告が審査中です")
            report = ReviewReport(
                report_id=secrets.token_hex(10),
                review_id=review_id,
                reporter_id=reporter_id,
                reason=reason,
                details=details.strip()[:1000],
            )
            self._review_reports[report.report_id] = report
        logger.info("Review reported: %s (reason=%s)", review_id, reason)
        return report

    def get_review_reports(
        self, status: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        """List review moderation reports (admin)."""
        with self._lock:
            items = list(self._review_reports.values())
        if status:
            items = [r for r in items if r.status == status]
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

    def resolve_review_report(
        self,
        report_id: str,
        moderator_id: str,
        action: str,  # "resolved" | "dismissed"
        note: str = "",
        *,
        hide: bool = False,
    ) -> ReviewReport:
        """Resolve a review report. If hide=True, hides the review as well."""
        if action not in ("resolved", "dismissed"):
            raise ValueError("action は 'resolved' または 'dismissed' のいずれかです")
        with self._lock:
            report = self._review_reports.get(report_id)
            if not report:
                raise ValueError("報告が見つかりません")
            if report.status != "pending":
                raise ValueError("この報告はすでに処理済みです")
            report.status = action
            report.resolved_by = moderator_id
            report.resolution_note = note.strip()[:1000]
            report.resolved_at = datetime.now(timezone.utc)
            if hide:
                rv = self._find_review(report.review_id)
                if rv and not rv.is_hidden:
                    rv.is_hidden = True
                    self._recompute_rating_locked(rv.listing_id)
        return report

    # --- Promo codes ---

    _MAX_PROMO_CODES_PER_CREATOR = 50
    _MAX_REPLIES_PER_REVIEW = 100

    def _resolve_promo(
        self, code_upper: str, listing_id: str, creator_id: str
    ) -> Optional["PromoCode"]:
        """Return a valid PromoCode for the listing, or None."""
        for pc in self._promo_codes.values():
            if (pc.code == code_upper and pc.creator_id == creator_id and pc.is_valid()
                    and (pc.listing_id is None or pc.listing_id == listing_id)):
                return pc
        return None

    def create_promo_code(
        self,
        creator_id: str,
        code: str,
        discount_percent: int,
        listing_id: Optional[str] = None,
        max_uses: Optional[int] = None,
        expires_at: Optional[datetime] = None,
    ) -> PromoCode:
        """Create a promo code. Only the listing owner may create listing-specific codes."""
        code = code.upper().strip()
        if not code or not code.isalnum():
            raise ValueError("コードは英数字のみ使用できます")
        if len(code) > 32:
            raise ValueError("コードは32文字以内にしてください")
        if not 1 <= discount_percent <= 99:
            raise ValueError("割引率は1〜99の範囲で指定してください")
        if max_uses is not None and max_uses < 1:
            raise ValueError("最大使用回数は1以上にしてください")
        # Normalize a naive expiry to UTC-aware: is_valid() compares against an
        # aware now(), and mixing naive/aware datetimes raises TypeError, which
        # would crash every purchase that applies this promo.
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        with self._lock:
            if listing_id:
                listing = self._listings.get(listing_id)
                if not listing or not listing.is_active:
                    raise ValueError("リスティングが見つかりません")
                if listing.owner_id != creator_id:
                    raise PermissionError("このリスティングのオーナーのみがプロモコードを作成できます")
            creator_codes = [pc for pc in self._promo_codes.values() if pc.creator_id == creator_id]
            if len(creator_codes) >= self._MAX_PROMO_CODES_PER_CREATOR:
                raise ValueError(f"プロモコードは最大{self._MAX_PROMO_CODES_PER_CREATOR}個まで作成できます")
            # Prevent duplicate active codes for the same creator
            for pc in creator_codes:
                if pc.code == code and pc.is_active:
                    raise ValueError(f"コード '{code}' はすでに存在します")
            promo = PromoCode(
                code_id=secrets.token_hex(8),
                code=code,
                creator_id=creator_id,
                discount_percent=discount_percent,
                listing_id=listing_id,
                max_uses=max_uses,
                expires_at=expires_at,
            )
            self._promo_codes[promo.code_id] = promo
        logger.info("Promo code created: %s by %s", code, creator_id)
        return promo

    def deactivate_promo_code(self, code_id: str, requester_id: str) -> PromoCode:
        """Deactivate a promo code (only the creator can do this)."""
        with self._lock:
            pc = self._promo_codes.get(code_id)
            if not pc:
                raise ValueError("プロモコードが見つかりません")
            if pc.creator_id != requester_id:
                raise PermissionError("このプロモコードのオーナーのみが無効化できます")
            pc.is_active = False
        return pc

    def list_promo_codes(self, creator_id: str) -> List[Dict[str, Any]]:
        """List all promo codes created by a creator."""
        with self._lock:
            codes = [pc for pc in self._promo_codes.values() if pc.creator_id == creator_id]
        codes.sort(key=lambda pc: pc.created_at, reverse=True)
        return [pc.to_dict() for pc in codes]

    def lookup_promo_code(self, code: str, listing_id: str) -> Optional[Dict[str, Any]]:
        """Public lookup: validate a code for a specific listing. Returns info or None."""
        code_upper = code.upper().strip()
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_active:
                return None
            pc = self._resolve_promo(code_upper, listing_id, listing.owner_id)
        if not pc:
            return None
        discount = max(0, min(99, pc.discount_percent))
        discounted = max(0, int(listing.price_credits * (100 - discount) / 100))
        return {
            "code": pc.code,
            "discount_percent": pc.discount_percent,
            "original_price": listing.price_credits,
            "discounted_price": discounted,
            "listing_id": listing_id,
        }

    # --- Tips ---

    _MAX_TIP_AMOUNT = 10_000
    _MAX_TIP_MESSAGE_LEN = 300

    def send_tip(
        self,
        sender_id: str,
        sender_username: str,
        recipient_id: str,
        amount: int,
        message: str = "",
    ) -> Tip:
        """Transfer credits from sender to recipient as a tip with an optional message."""
        if sender_id == recipient_id:
            raise ValueError("自分自身にチップを送ることはできません")
        if amount <= 0:
            raise ValueError("チップは1クレジット以上にしてください")
        if amount > self._MAX_TIP_AMOUNT:
            raise ValueError(f"1回のチップは{self._MAX_TIP_AMOUNT}クレジットまでです")
        message = message.strip()[:self._MAX_TIP_MESSAGE_LEN]
        tip = Tip(
            tip_id=secrets.token_hex(8),
            sender_id=sender_id,
            sender_username=sender_username,
            recipient_id=recipient_id,
            amount=amount,
            message=message,
        )
        # Credit transfer and tip record creation are atomic: either both happen or neither.
        with self._lock:
            self._debit_locked(sender_id, amount, "tip_sent", ref_id=recipient_id)
            self._credit_locked(recipient_id, amount, "tip_received", ref_id=sender_id)
            self._tips.append(tip)
        logger.info("Tip sent: %s → %s (%d credits)", sender_id, recipient_id, amount)
        return tip

    def get_tips_received(
        self, recipient_id: str, limit: int = 20, offset: int = 0, *, public: bool = False
    ) -> Dict[str, Any]:
        """Return paginated tips received by a user, newest first.

        With ``public=True`` each item is the public-safe view (no sender_id,
        no private message) for the unauthenticated tips feed.
        """
        with self._lock:
            items = [t for t in self._tips if t.recipient_id == recipient_id]
        items = list(reversed(items))  # newest first
        total = len(items)
        offset, limit = normalize_pagination(offset, limit)
        page = items[offset: offset + limit]
        has_more = offset + limit < total
        render = (lambda t: t.to_public_dict()) if public else (lambda t: t.to_dict())
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [render(t) for t in page],
        }

    def get_tips_sent(
        self, sender_id: str, limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """Return paginated tips sent by a user, newest first."""
        with self._lock:
            items = [t for t in self._tips if t.sender_id == sender_id]
        items = list(reversed(items))  # newest first
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
            "items": [t.to_dict() for t in page],
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_marketplace: Optional[MarketplaceStore] = None
_marketplace_lock = threading.Lock()


def get_marketplace() -> MarketplaceStore:
    global _marketplace
    if _marketplace is None:
        with _marketplace_lock:
            if _marketplace is None:
                _marketplace = MarketplaceStore()
    return _marketplace
