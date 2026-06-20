"""License key system for purchased avatar listings.

When a buyer downloads a paid listing a LicenseKey is issued automatically.
The key:
  - Is tied to (listing_id, buyer_id) — one key per buyer per listing.
  - Can be revoked by the listing owner or an admin.
  - Can optionally have a max_activations limit (default: unlimited).
  - Records each 'activation' event (e.g. installing on a VRChat world).

This module is pure stdlib with no external deps.
"""
from __future__ import annotations

import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from .pagination import normalize_pagination
except ImportError:  # pragma: no cover - support flat import in tests
    from pagination import normalize_pagination

logger = logging.getLogger(__name__)

_KEY_PREFIX = "CCA"       # Cocoa Avatar
_KEY_HEX_BYTES = 12       # 24 hex chars → "CCA-XXXXXXXX-XXXXXXXX-XXXXXXXX"
_MAX_ACTIVATION_NOTES_LEN = 200


def _generate_key() -> str:
    raw = secrets.token_hex(_KEY_HEX_BYTES).upper()
    return f"{_KEY_PREFIX}-{raw[:8]}-{raw[8:16]}-{raw[16:24]}"


@dataclass
class LicenseActivation:
    activation_id: str
    note: str = ""  # e.g. "VRChat world Fantasia"
    activated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "activation_id": self.activation_id,
            "note": self.note,
            "activated_at": self.activated_at.isoformat(),
        }


@dataclass
class LicenseKey:
    key_id: str
    key: str
    listing_id: str
    owner_id: str        # listing creator
    holder_id: str       # the buyer
    max_activations: Optional[int] = None  # None = unlimited
    is_revoked: bool = False
    revoked_by: str = ""
    revoked_reason: str = ""
    activations: List[LicenseActivation] = field(default_factory=list)
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    revoked_at: Optional[datetime] = None

    def activation_count(self) -> int:
        return len(self.activations)

    def can_activate(self) -> bool:
        if self.is_revoked:
            return False
        return not (self.max_activations is not None and len(self.activations) >= self.max_activations)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": self.key_id,
            "key": self.key,
            "listing_id": self.listing_id,
            "owner_id": self.owner_id,
            "holder_id": self.holder_id,
            "max_activations": self.max_activations,
            "activation_count": self.activation_count(),
            "is_revoked": self.is_revoked,
            "revoked_by": self.revoked_by,
            "revoked_reason": self.revoked_reason,
            "activations": [a.to_dict() for a in self.activations],
            "issued_at": self.issued_at.isoformat(),
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }


class LicenseStore:
    """Thread-safe in-memory license store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: Dict[str, LicenseKey] = {}          # key_id → LicenseKey
        self._by_key: Dict[str, str] = {}               # key_string → key_id
        self._holder_keys: Dict[str, List[str]] = {}    # holder_id → [key_id]
        self._listing_keys: Dict[str, List[str]] = {}   # listing_id → [key_id]
        self._listing_owner: Dict[str, str] = {}        # listing_id → owner_id
        # (listing_id, holder_id) → key_id for uniqueness check
        self._pair_key: Dict[tuple, str] = {}

    def issue_key(
        self,
        listing_id: str,
        owner_id: str,
        holder_id: str,
        max_activations: Optional[int] = None,
    ) -> LicenseKey:
        """Issue a new license key.  If a key already exists for this
        (listing_id, holder_id) pair, return the existing one."""
        with self._lock:
            pair = (listing_id, holder_id)
            if pair in self._pair_key:
                return self._keys[self._pair_key[pair]]

            raw = _generate_key()
            while raw in self._by_key:
                raw = _generate_key()

            lk = LicenseKey(
                key_id=secrets.token_hex(8),
                key=raw,
                listing_id=listing_id,
                owner_id=owner_id,
                holder_id=holder_id,
                max_activations=max_activations,
            )
            self._keys[lk.key_id] = lk
            self._by_key[raw] = lk.key_id
            self._holder_keys.setdefault(holder_id, []).append(lk.key_id)
            self._listing_keys.setdefault(listing_id, []).append(lk.key_id)
            self._listing_owner.setdefault(listing_id, owner_id)
            self._pair_key[pair] = lk.key_id
            return lk

    def get_by_id(self, key_id: str) -> Optional[LicenseKey]:
        with self._lock:
            return self._keys.get(key_id)

    def get_by_key_string(self, key: str) -> Optional[LicenseKey]:
        with self._lock:
            kid = self._by_key.get(key.upper())
            return self._keys.get(kid) if kid else None

    def get_holder_keys(
        self, holder_id: str, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        with self._lock:
            ids = list(reversed(self._holder_keys.get(holder_id, [])))
            total = len(ids)
            offset, limit = normalize_pagination(offset, limit)
            page = [self._keys[i].to_dict() for i in ids[offset: offset + limit] if i in self._keys]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": page,
        }

    def get_listing_keys(
        self, listing_id: str, owner_id: str, limit: int = 100, offset: int = 0
    ) -> Dict[str, Any]:
        """Owner-only view of all keys issued for a listing."""
        with self._lock:
            ids = self._listing_keys.get(listing_id, [])
            all_keys = [self._keys[i] for i in ids if i in self._keys]
            known_owner = (
                all_keys[0].owner_id if all_keys
                else self._listing_owner.get(listing_id)
            )
            if known_owner is not None and known_owner != owner_id:
                raise PermissionError("このリスティングのオーナーのみがライセンスを確認できます")
            total = len(all_keys)
            offset, limit = normalize_pagination(offset, limit)
            page = all_keys[offset: offset + limit]
            serialized = [k.to_dict() for k in page]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": serialized,
        }

    def activate(self, key_id: str, holder_id: str, note: str = "") -> LicenseKey:
        """Record an activation event."""
        with self._lock:
            lk = self._keys.get(key_id)
            if not lk:
                raise ValueError("ライセンスキーが見つかりません")
            if lk.holder_id != holder_id:
                raise PermissionError("このライセンスキーの所有者ではありません")
            if lk.is_revoked:
                raise ValueError("このライセンスキーは失効しています")
            if lk.max_activations is not None and len(lk.activations) >= lk.max_activations:
                raise ValueError(f"アクティベーション上限({lk.max_activations})に達しています")
            activation = LicenseActivation(
                activation_id=secrets.token_hex(6),
                note=note.strip()[:_MAX_ACTIVATION_NOTES_LEN],
            )
            lk.activations.append(activation)
            return lk

    def revoke(
        self, key_id: str, revoker_id: str, reason: str = "", is_admin: bool = False
    ) -> LicenseKey:
        """Revoke a license key.  revoker_id must be owner_id or admin.

        Raises ValueError if the key is already revoked — preserves the original
        revocation audit record and prevents an owner from overwriting an admin revocation.
        """
        with self._lock:
            lk = self._keys.get(key_id)
            if not lk:
                raise ValueError("ライセンスキーが見つかりません")
            if lk.is_revoked:
                raise ValueError("このライセンスキーはすでに失効しています")
            if not is_admin and lk.owner_id != revoker_id:
                raise PermissionError("このライセンスキーを失効させる権限がありません")
            lk.is_revoked = True
            lk.revoked_by = revoker_id
            lk.revoked_reason = reason.strip()[:500]
            lk.revoked_at = datetime.now(timezone.utc)
            return lk

    def verify(self, key: str) -> Dict[str, Any]:
        """Verify whether a key string is valid and not revoked."""
        with self._lock:
            kid = self._by_key.get(key.upper())
            lk = self._keys.get(kid) if kid else None
            if not lk:
                return {"valid": False, "reason": "not_found"}
            if lk.is_revoked:
                return {"valid": False, "reason": "revoked"}
            # Read every field under the lock so the verdict and the returned
            # counts are a consistent snapshot — a concurrent revoke()/activate()
            # can't slip between the is_revoked check and the field reads.
            return {
                "valid": True,
                "key_id": lk.key_id,
                "listing_id": lk.listing_id,
                "holder_id": lk.holder_id,
                "activation_count": lk.activation_count(),
                "max_activations": lk.max_activations,
            }


class LicenseManager:
    """Business logic for license issuance and management."""

    def __init__(self, store: Optional[LicenseStore] = None) -> None:
        self.store = store or LicenseStore()

    def issue_on_download(
        self,
        listing_id: str,
        owner_id: str,
        buyer_id: str,
        max_activations: Optional[int] = None,
    ) -> LicenseKey:
        """Issue (or return existing) license for a download."""
        return self.store.issue_key(listing_id, owner_id, buyer_id, max_activations)

    def activate_key(self, key_id: str, holder_id: str, note: str = "") -> Dict[str, Any]:
        return self.store.activate(key_id, holder_id, note).to_dict()

    def revoke_key(
        self, key_id: str, revoker_id: str, reason: str = "", is_admin: bool = False
    ) -> Dict[str, Any]:
        return self.store.revoke(key_id, revoker_id, reason, is_admin).to_dict()

    def verify_key(self, key: str) -> Dict[str, Any]:
        return self.store.verify(key)

    def get_my_licenses(self, user_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        return self.store.get_holder_keys(user_id, limit=limit, offset=offset)

    def get_listing_licenses(
        self, listing_id: str, owner_id: str, limit: int = 100, offset: int = 0
    ) -> Dict[str, Any]:
        return self.store.get_listing_keys(listing_id, owner_id, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_license_manager: Optional[LicenseManager] = None
_lm_lock = threading.Lock()


def get_license_manager() -> LicenseManager:
    global _license_manager
    if _license_manager is None:
        with _lm_lock:
            if _license_manager is None:
                _license_manager = LicenseManager()
    return _license_manager
