"""
JWT-based Authentication Manager for Cocoa

Features:
- User registration with password hashing (bcrypt)
- Login with JWT access + refresh token pair
- Token refresh flow
- Role-based access control (user / moderator / admin)
- Revocation via in-memory denylist (swap for Redis in prod)
- Password reset token generation
"""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

try:
    from .pagination import normalize_pagination
except ImportError:  # pragma: no cover - support flat import in tests
    from pagination import normalize_pagination

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional deps
# ---------------------------------------------------------------------------
try:
    import bcrypt
    _BCRYPT_AVAILABLE = True
except ImportError:
    _BCRYPT_AVAILABLE = False

try:
    import jwt as _jwt
    _JWT_AVAILABLE = True
except BaseException:
    _jwt = None
    _JWT_AVAILABLE = False

# ---------------------------------------------------------------------------
# Config (override via env)
# ---------------------------------------------------------------------------
_SECRET_KEY = os.getenv("COCOA_JWT_SECRET", secrets.token_hex(32))
_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
_RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "15"))

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
ROLES = ("user", "moderator", "admin")


_ALLOWED_SOCIAL_KEYS = frozenset({"twitter", "vrchat", "github", "website", "youtube", "twitch"})

_MAX_BOOKMARKS = int(os.getenv("MAX_BOOKMARKS", "1000"))
_MAX_FOLLOWING = int(os.getenv("MAX_FOLLOWING", "2000"))


@dataclass
class CreatorApplication:
    application_id: str
    user_id: str
    username: str
    reason: str          # why they want to become a creator
    portfolio_url: str
    status: str = "pending"   # pending | approved | rejected
    reviewed_by: str = ""
    review_note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "application_id": self.application_id,
            "user_id": self.user_id,
            "username": self.username,
            "reason": self.reason,
            "portfolio_url": self.portfolio_url,
            "status": self.status,
            "reviewed_by": self.reviewed_by,
            "review_note": self.review_note,
            "created_at": self.created_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }


@dataclass
class UserRecord:
    user_id: str
    username: str
    email: str
    password_hash: str
    role: str = "user"
    is_active: bool = True
    is_email_verified: bool = False
    is_creator_verified: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None
    failed_attempts: int = 0
    locked_until: Optional[datetime] = None
    display_name: str = ""
    bio: str = ""
    avatar_url: str = ""
    website_url: str = ""
    social_links: Dict[str, str] = field(default_factory=dict)  # e.g. {"twitter": "@alice"}
    bookmarks: List[str] = field(default_factory=list)  # list of doc_ids / listing_ids
    following: List[str] = field(default_factory=list)   # list of user_ids this user follows
    followed_tags: List[str] = field(default_factory=list)  # tag strings user follows
    is_banned: bool = False
    ban_reason: str = ""
    banned_at: Optional[datetime] = None
    banned_by: str = ""

    def is_locked(self) -> bool:
        return bool(self.locked_until and datetime.now(timezone.utc) < self.locked_until)

    def public_profile(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name or self.username,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "website_url": self.website_url,
            "social_links": dict(self.social_links),
            "role": self.role,
            "is_email_verified": self.is_email_verified,
            "is_creator_verified": self.is_creator_verified,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = _ACCESS_TOKEN_EXPIRE_MINUTES * 60


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash a password with bcrypt (or PBKDF2 fallback)."""
    if _BCRYPT_AVAILABLE:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()
    # PBKDF2 fallback
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"pbkdf2${salt}${dk.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against stored hash."""
    try:
        if _BCRYPT_AVAILABLE and hashed.startswith("$2"):
            return bcrypt.checkpw(password.encode(), hashed.encode())
        if hashed.startswith("pbkdf2$"):
            _, salt, stored_dk = hashed.split("$")
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
            return hmac.compare_digest(dk.hex(), stored_dk)
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# JWT utilities (with pure-Python fallback)
# ---------------------------------------------------------------------------
def _encode_token(payload: Dict[str, Any]) -> str:
    if _JWT_AVAILABLE:
        return _jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)
    # Minimal HS256 implementation (for envs without PyJWT)
    import base64
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    msg = header + b"." + body
    sig = hmac.new(_SECRET_KEY.encode(), msg, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=")
    return (msg + b"." + sig_b64).decode()


def _decode_token(token: str) -> Dict[str, Any]:
    if _JWT_AVAILABLE:
        return _jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    import base64 as _b64

    def _pad(s: str) -> bytes:
        return (s + "=" * (4 - len(s) % 4)).encode()

    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")
    header_b, body_b, sig_b = parts
    msg = f"{header_b}.{body_b}".encode()
    expected_sig = hmac.new(_SECRET_KEY.encode(), msg, hashlib.sha256).digest()
    actual_sig = _b64.urlsafe_b64decode(_pad(sig_b))
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid signature")
    payload = json.loads(_b64.urlsafe_b64decode(_pad(body_b)))
    if payload.get("exp", 0) < time.time():
        raise ValueError("Token expired")
    return payload


def create_access_token(user_id: str, username: str, role: str, extra: Optional[Dict] = None) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "jti": secrets.token_hex(16),
    }
    if extra:
        payload.update(extra)
    return _encode_token(payload)


def create_refresh_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": user_id,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS)).timestamp()),
        "jti": secrets.token_hex(16),
    }
    return _encode_token(payload)


def decode_access_token(token: str) -> Dict[str, Any]:
    payload = _decode_token(token)
    if payload.get("type") != "access":
        raise ValueError("Not an access token")
    return payload


def decode_refresh_token(token: str) -> Dict[str, Any]:
    payload = _decode_token(token)
    if payload.get("type") != "refresh":
        raise ValueError("Not a refresh token")
    return payload


# ---------------------------------------------------------------------------
# In-memory user store (swap for DB in production)
# ---------------------------------------------------------------------------
class UserStore:
    """Thread-safe in-memory user store with lookup by id / username / email."""

    def __init__(self):
        self._by_id: Dict[str, UserRecord] = {}
        self._by_username: Dict[str, str] = {}  # username → user_id
        self._by_email: Dict[str, str] = {}      # email → user_id
        self._revoked_jtis: Dict[str, float] = {}  # jti → expiry timestamp
        self._reset_tokens: Dict[str, tuple] = {}  # token → (user_id, exp)
        self._verify_tokens: Dict[str, tuple] = {}  # token → (user_id, exp)
        self._api_keys: Dict[str, Dict] = {}          # key_id → {user_id, name, key_id, key_hash, ...}
        self._api_key_by_hash: Dict[str, str] = {}    # key_hash → key_id (O(1) lookup)
        self._api_keys_by_user: Dict[str, List[str]] = {}  # user_id → [key_id] (per-user cap)
        self._applications: Dict[str, CreatorApplication] = {}  # application_id → CreatorApplication

    # --- CRUD ---

    @staticmethod
    def _uname_key(username: str) -> str:
        """Case-insensitive, whitespace-trimmed key for username uniqueness/lookup
        so 'alice', 'Alice', and ' alice ' resolve to one account (anti-impersonation)."""
        return username.strip().casefold()

    @staticmethod
    def _email_key(email: str) -> str:
        """Normalized email (trimmed, lowercased) so 'Alice@X.com' and 'alice@x.com'
        are one account and password-reset/login-by-email can't miss on casing."""
        return email.strip().lower()

    def create_user(self, username: str, email: str, password: str, role: str = "user") -> UserRecord:
        username = username.strip()
        email = self._email_key(email)
        if not (1 <= len(username) <= 64):
            raise ValueError("ユーザー名は1〜64文字にしてください")
        if len(email) > 254:
            raise ValueError("メールアドレスが長すぎます (最大254文字)")
        if len(password) > 1024:
            raise ValueError("パスワードが長すぎます (最大1024文字)")
        if self._uname_key(username) in self._by_username:
            raise ValueError(f"Username '{username}' already exists")
        if email in self._by_email:
            raise ValueError(f"Email '{email}' already registered")
        if role not in ROLES:
            raise ValueError(f"Unknown role '{role}'")

        user = UserRecord(
            user_id=secrets.token_hex(16),
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        self._by_id[user.user_id] = user
        self._by_username[self._uname_key(username)] = user.user_id
        self._by_email[email] = user.user_id
        logger.info("User created: %s (role=%s)", username, role)
        return user

    def get_by_id(self, user_id: str) -> Optional[UserRecord]:
        return self._by_id.get(user_id)

    def get_by_username(self, username: str) -> Optional[UserRecord]:
        uid = self._by_username.get(self._uname_key(username))
        return self._by_id.get(uid) if uid else None

    def get_by_email(self, email: str) -> Optional[UserRecord]:
        uid = self._by_email.get(self._email_key(email))
        return self._by_id.get(uid) if uid else None

    def list_users(self) -> List[UserRecord]:
        return list(self._by_id.values())

    def delete_user(self, user_id: str) -> bool:
        user = self._by_id.pop(user_id, None)
        if user:
            # user.username/email are stored already-normalized; key the same way.
            self._by_username.pop(self._uname_key(user.username), None)
            self._by_email.pop(self._email_key(user.email), None)
            return True
        return False

    # --- Token revocation ---

    def revoke_jti(self, jti: str, exp: Optional[float] = None) -> None:
        if exp is None:
            exp = time.time() + _REFRESH_TOKEN_EXPIRE_DAYS * 86400
        self._revoked_jtis[jti] = exp

    def is_revoked(self, jti: str) -> bool:
        now = time.time()
        # Prune expired JTIs so the set doesn't grow forever.
        expired = [k for k, e in self._revoked_jtis.items() if e < now]
        for k in expired:
            del self._revoked_jtis[k]
        return jti in self._revoked_jtis

    # --- Password reset ---

    def create_reset_token(self, user_id: str) -> str:
        # Invalidate all existing tokens for this user before issuing a new one.
        # Prevents token accumulation from repeated reset requests and ensures
        # only the most recent link works (phishing-resistant).
        stale = [t for t, (uid, _) in self._reset_tokens.items() if uid == user_id]
        for t in stale:
            del self._reset_tokens[t]
        token = secrets.token_urlsafe(32)
        exp = time.time() + _RESET_TOKEN_EXPIRE_MINUTES * 60
        self._reset_tokens[token] = (user_id, exp)
        return token

    def consume_reset_token(self, token: str) -> Optional[str]:
        entry = self._reset_tokens.pop(token, None)
        if entry and entry[1] > time.time():
            return entry[0]
        return None

    # --- Email verification ---

    _VERIFY_TOKEN_EXPIRE_MINUTES: int = 24 * 60  # 24 hours

    def create_verify_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        exp = time.time() + self._VERIFY_TOKEN_EXPIRE_MINUTES * 60
        self._verify_tokens[token] = (user_id, exp)
        return token

    def consume_verify_token(self, token: str) -> Optional[str]:
        entry = self._verify_tokens.pop(token, None)
        if entry and entry[1] > time.time():
            return entry[0]
        return None

    # --- API key management ---

    _MAX_API_KEYS_PER_USER = 10

    def create_api_key(self, user_id: str, name: str) -> Dict[str, Any]:
        """Create a new API key. Returns the raw key ONCE — it is never stored."""
        user_keys = self._api_keys_by_user.get(user_id, [])
        if len(user_keys) >= self._MAX_API_KEYS_PER_USER:
            raise ValueError(f"APIキーは最大{self._MAX_API_KEYS_PER_USER}個まで作成できます")
        raw_key = "cca_" + secrets.token_urlsafe(32)
        key_id = secrets.token_hex(8)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:12]
        entry: Dict[str, Any] = {
            "key_id": key_id,
            "user_id": user_id,
            "name": name,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_used": None,
        }
        self._api_keys[key_id] = entry
        self._api_key_by_hash[key_hash] = key_id
        self._api_keys_by_user.setdefault(user_id, []).append(key_id)
        return {k: v for k, v in entry.items() if k != "key_hash"} | {"raw_key": raw_key}

    def revoke_api_key(self, user_id: str, key_id: str) -> bool:
        entry = self._api_keys.get(key_id)
        if not entry or entry["user_id"] != user_id:
            return False
        del self._api_keys[key_id]
        self._api_key_by_hash.pop(entry["key_hash"], None)
        user_ids = self._api_keys_by_user.get(user_id, [])
        with contextlib.suppress(ValueError):
            user_ids.remove(key_id)
        return True

    def list_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        return [
            {k: v for k, v in self._api_keys[kid].items() if k != "key_hash"}
            for kid in self._api_keys_by_user.get(user_id, [])
            if kid in self._api_keys
        ]

    def verify_api_key(self, raw_key: str) -> Optional[Dict[str, Any]]:
        """Verify a raw API key and return a JWT-like payload dict, or None."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_id = self._api_key_by_hash.get(key_hash)
        if key_id is None:
            return None
        entry = self._api_keys.get(key_id)
        if entry is None:
            return None
        entry["last_used"] = datetime.now(timezone.utc).isoformat()
        user = self._by_id.get(entry["user_id"])
        if not user or not user.is_active or user.is_banned:
            return None
        return {
            "sub": user.user_id,
            "username": user.username,
            "role": user.role,
            "type": "api_key",
            "key_id": entry["key_id"],
        }


# ---------------------------------------------------------------------------
# AuthManager facade
# ---------------------------------------------------------------------------
_MAX_FAILED = int(os.getenv("AUTH_MAX_FAILED_ATTEMPTS", "5"))
_LOCKOUT_MINUTES = int(os.getenv("AUTH_LOCKOUT_MINUTES", "15"))


class AuthManager:
    """
    Central authentication manager.

    Usage:
        auth = AuthManager()
        tokens = auth.login("alice", "hunter2")
        payload = auth.verify_access_token(tokens.access_token)
        new_tokens = auth.refresh(tokens.refresh_token)
        auth.logout(tokens.access_token, tokens.refresh_token)
    """

    def __init__(self, store: Optional[UserStore] = None, max_failed_attempts: Optional[int] = None, lockout_minutes: Optional[int] = None):
        self.store = store or UserStore()
        self._max_failed = max_failed_attempts if max_failed_attempts is not None else _MAX_FAILED
        self._lockout_minutes = lockout_minutes if lockout_minutes is not None else _LOCKOUT_MINUTES

    # --- Registration ---

    def register(self, username: str, email: str, password: str, role: str = "user") -> UserRecord:
        self._validate_password_strength(password)
        return self.store.create_user(username, email, password, role)

    # --- Login / Logout ---

    def login(self, username: str, password: str) -> TokenPair:
        user = self.store.get_by_username(username)
        if not user:
            raise AuthError("invalid_credentials", "ユーザー名またはパスワードが正しくありません")

        if not user.is_active:
            raise AuthError("account_disabled", "アカウントが無効です")

        if user.is_banned:
            raise AuthError("account_banned", f"アカウントが停止されています: {user.ban_reason}" if user.ban_reason else "アカウントが停止されています")

        if user.is_locked():
            remaining = int((user.locked_until - datetime.now(timezone.utc)).total_seconds())
            raise AuthError("account_locked", f"アカウントがロックされています（{remaining}秒後に解除）")

        if not verify_password(password, user.password_hash):
            user.failed_attempts += 1
            if user.failed_attempts >= self._max_failed:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=self._lockout_minutes)
                logger.warning("Account locked after %d failed attempts: %s", self._max_failed, username)
            raise AuthError("invalid_credentials", "ユーザー名またはパスワードが正しくありません")

        # Reset on success
        user.failed_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(timezone.utc)

        access = create_access_token(user.user_id, user.username, user.role)
        refresh = create_refresh_token(user.user_id)
        logger.info("Login successful: %s", username)
        return TokenPair(access_token=access, refresh_token=refresh)

    def logout(self, access_token: str, refresh_token: Optional[str] = None) -> None:
        for tok in [t for t in [access_token, refresh_token] if t]:
            try:
                payload = _decode_token(tok)
                jti = payload.get("jti")
                if jti:
                    self.store.revoke_jti(jti, exp=payload.get("exp"))
            except Exception:
                pass
        logger.debug("Tokens revoked (logout)")

    # --- Token management ---

    def verify_access_token(self, token: str) -> Dict[str, Any]:
        payload = decode_access_token(token)
        jti = payload.get("jti", "")
        if self.store.is_revoked(jti):
            raise AuthError("token_revoked", "トークンは無効化されました")
        user = self.store.get_by_id(payload["sub"])
        if not user or not user.is_active:
            raise AuthError("account_disabled", "アカウントが無効です")
        if user.is_banned:
            raise AuthError("account_banned", "アカウントが停止されています")
        # Override the JWT-embedded role with the live value from the store so
        # role changes (promotions and demotions) take effect immediately without
        # waiting for the token to expire.
        payload["role"] = user.role
        return payload

    def refresh(self, refresh_token: str) -> TokenPair:
        payload = decode_refresh_token(refresh_token)
        jti = payload.get("jti", "")
        if self.store.is_revoked(jti):
            raise AuthError("token_revoked", "リフレッシュトークンは無効化されました")

        user = self.store.get_by_id(payload["sub"])
        if not user or not user.is_active:
            raise AuthError("account_disabled", "アカウントが無効です")
        if user.is_banned:
            raise AuthError("account_banned", "アカウントが停止されています")

        # Rotate refresh token
        self.store.revoke_jti(jti, exp=payload.get("exp"))
        new_access = create_access_token(user.user_id, user.username, user.role)
        new_refresh = create_refresh_token(user.user_id)
        return TokenPair(access_token=new_access, refresh_token=new_refresh)

    # --- Password reset ---

    def request_password_reset(self, email: str) -> Optional[str]:
        user = self.store.get_by_email(email)
        if not user:
            return None  # Don't leak existence
        token = self.store.create_reset_token(user.user_id)
        logger.info("Password reset token generated for: %s", email)
        return token

    def reset_password(self, reset_token: str, new_password: str) -> bool:
        user_id = self.store.consume_reset_token(reset_token)
        if not user_id:
            return False
        user = self.store.get_by_id(user_id)
        if not user:
            return False
        self._validate_password_strength(new_password)
        user.password_hash = hash_password(new_password)
        logger.info("Password reset for user_id: %s", user_id)
        return True

    # --- Email verification ---

    def create_email_verification_token(self, user_id: str) -> str:
        return self.store.create_verify_token(user_id)

    def verify_email(self, token: str) -> bool:
        user_id = self.store.consume_verify_token(token)
        if not user_id:
            return False
        user = self.store.get_by_id(user_id)
        if not user:
            return False
        user.is_email_verified = True
        logger.info("Email verified for user_id: %s", user_id)
        return True

    # --- Role management ---

    def require_role(self, payload: Dict[str, Any], *roles: str) -> None:
        user_role = payload.get("role", "user")
        if user_role not in roles:
            raise AuthError("forbidden", f"このリソースには{'/'.join(roles)}ロールが必要です")

    def change_role(self, admin_payload: Dict[str, Any], target_user_id: str, new_role: str) -> None:
        self.require_role(admin_payload, "admin")
        if new_role not in ROLES:
            raise ValueError(f"Unknown role: {new_role}")
        user = self.store.get_by_id(target_user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        user.role = new_role
        logger.info("Role changed for %s → %s (by admin %s)", target_user_id, new_role, admin_payload.get("username"))

    # --- Profile management ---

    def update_profile(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        bio: Optional[str] = None,
        avatar_url: Optional[str] = None,
        website_url: Optional[str] = None,
        social_links: Optional[Dict[str, str]] = None,
    ) -> UserRecord:
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        if display_name is not None:
            user.display_name = display_name[:64].strip()
        if bio is not None:
            user.bio = bio[:500].strip()
        if avatar_url is not None:
            user.avatar_url = avatar_url[:512].strip()
        if website_url is not None:
            user.website_url = website_url[:512].strip()
        if social_links is not None:
            sanitized = {
                k: str(v)[:200].strip()
                for k, v in social_links.items()
                if k in _ALLOWED_SOCIAL_KEYS
            }
            user.social_links = sanitized
        logger.info("Profile updated for user_id: %s", user_id)
        return user

    # --- Bookmarks ---

    def add_bookmark(self, user_id: str, item_id: str) -> List[str]:
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        if item_id not in user.bookmarks:
            if len(user.bookmarks) >= _MAX_BOOKMARKS:
                raise ValueError(f"ブックマークは最大{_MAX_BOOKMARKS}件までです")
            user.bookmarks.append(item_id)
        return list(user.bookmarks)

    def remove_bookmark(self, user_id: str, item_id: str) -> List[str]:
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        with contextlib.suppress(ValueError):
            user.bookmarks.remove(item_id)
        return list(user.bookmarks)

    def get_bookmarks(self, user_id: str) -> List[str]:
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        return list(user.bookmarks)

    def get_users_who_bookmarked(self, item_id: str) -> List[str]:
        """Return user_ids of all users who have item_id in their bookmarks."""
        return [u.user_id for u in self.store.list_users() if item_id in u.bookmarks]

    # --- Following ---

    def follow(self, follower_id: str, creator_id: str) -> List[str]:
        follower = self.store.get_by_id(follower_id)
        if not follower:
            raise AuthError("not_found", "ユーザーが見つかりません")
        if follower_id == creator_id:
            raise ValueError("自分自身をフォローすることはできません")
        creator = self.store.get_by_id(creator_id)
        if not creator:
            raise AuthError("not_found", "フォロー先ユーザーが見つかりません")
        if creator_id not in follower.following:
            if len(follower.following) >= _MAX_FOLLOWING:
                raise ValueError(f"フォローできるユーザーは最大{_MAX_FOLLOWING}人です")
            follower.following.append(creator_id)
        return list(follower.following)

    def unfollow(self, follower_id: str, creator_id: str) -> List[str]:
        follower = self.store.get_by_id(follower_id)
        if not follower:
            raise AuthError("not_found", "ユーザーが見つかりません")
        with contextlib.suppress(ValueError):
            follower.following.remove(creator_id)
        return list(follower.following)

    def get_following(self, user_id: str) -> List[Dict[str, Any]]:
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        profiles = []
        for uid in user.following:
            creator = self.store.get_by_id(uid)
            if creator:
                profiles.append(creator.public_profile())
        return profiles

    def get_followers_count(self, user_id: str) -> int:
        return sum(1 for u in self.store.list_users() if user_id in u.following)

    def get_public_profile(self, user_id: str) -> Dict[str, Any]:
        """Return the public profile dict for user_id, raising AuthError if missing."""
        user = self.store.get_by_id(user_id)
        if not user or not user.is_active:
            raise AuthError("not_found", "ユーザーが見つかりません")
        profile = user.public_profile()
        profile["followers_count"] = self.get_followers_count(user_id)
        return profile

    def get_followers(self, user_id: str) -> List[Dict[str, Any]]:
        """Return public profiles of all users who follow user_id."""
        if not self.store.get_by_id(user_id):
            raise AuthError("not_found", "ユーザーが見つかりません")
        return [
            u.public_profile()
            for u in self.store.list_users()
            if user_id in u.following
        ]

    # --- Creator verification ---

    def verify_creator(self, admin_payload: Dict[str, Any], user_id: str) -> UserRecord:
        """Grant creator-verified badge (admin only)."""
        self.require_role(admin_payload, "admin")
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        user.is_creator_verified = True
        logger.info("Creator verified: %s (by admin %s)", user_id, admin_payload.get("username"))
        return user

    def revoke_creator_verification(self, admin_payload: Dict[str, Any], user_id: str) -> UserRecord:
        """Revoke creator-verified badge (admin only)."""
        self.require_role(admin_payload, "admin")
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        user.is_creator_verified = False
        logger.info("Creator verification revoked: %s (by admin %s)", user_id, admin_payload.get("username"))
        return user

    # --- Creator applications ---

    def submit_creator_application(
        self, user_id: str, reason: str, portfolio_url: str = ""
    ) -> CreatorApplication:
        """User submits a creator verification application. One pending application at a time."""
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        if user.is_creator_verified:
            raise ValueError("すでにクリエイター認定済みです")
        reason = reason.strip()[:1000]
        if not reason:
            raise ValueError("申請理由を入力してください")
        # Check for existing pending application
        for app in self.store._applications.values():
            if app.user_id == user_id and app.status == "pending":
                raise ValueError("すでに審査中の申請があります")
        application = CreatorApplication(
            application_id=secrets.token_hex(10),
            user_id=user_id,
            username=user.username,
            reason=reason,
            portfolio_url=portfolio_url.strip()[:512],
        )
        self.store._applications[application.application_id] = application
        logger.info("Creator application submitted by %s", user.username)
        return application

    def review_creator_application(
        self,
        admin_payload: Dict[str, Any],
        application_id: str,
        decision: str,  # "approved" | "rejected"
        note: str = "",
    ) -> CreatorApplication:
        """Admin approves or rejects a creator application."""
        self.require_role(admin_payload, "admin")
        if decision not in ("approved", "rejected"):
            raise ValueError("decision は 'approved' または 'rejected' のいずれかです")
        app = self.store._applications.get(application_id)
        if not app:
            raise ValueError("申請が見つかりません")
        if app.status != "pending":
            raise ValueError("この申請はすでに審査済みです")
        app.status = decision
        app.reviewed_by = admin_payload.get("sub", "")
        app.review_note = note.strip()[:500]
        app.reviewed_at = datetime.now(timezone.utc)
        if decision == "approved":
            user = self.store.get_by_id(app.user_id)
            if user:
                user.is_creator_verified = True
        logger.info("Creator application %s: %s by admin %s", application_id, decision, app.reviewed_by)
        return app

    def get_creator_applications(
        self,
        status: Optional[str] = None,  # pending | approved | rejected | None (all)
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Admin: list creator applications."""
        items = list(self.store._applications.values())
        if status:
            items = [a for a in items if a.status == status]
        items.sort(key=lambda a: a.created_at, reverse=True)
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
            "items": [a.to_dict() for a in page],
        }

    def get_my_creator_application(self, user_id: str) -> Optional[CreatorApplication]:
        """Return the most recent application submitted by user_id."""
        apps = [
            a for a in self.store._applications.values()
            if a.user_id == user_id
        ]
        return max(apps, key=lambda a: a.created_at, default=None)

    # --- Tag following ---

    _MAX_FOLLOWED_TAGS = 100

    def follow_tag(self, user_id: str, tag: str) -> List[str]:
        """Add a tag to the user's followed tags. Returns updated list."""
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        tag = tag.strip().lower()[:64]
        if not tag:
            raise ValueError("タグを入力してください")
        if tag not in user.followed_tags:
            if len(user.followed_tags) >= self._MAX_FOLLOWED_TAGS:
                raise ValueError(f"フォローできるタグは最大{self._MAX_FOLLOWED_TAGS}個です")
            user.followed_tags.append(tag)
        return list(user.followed_tags)

    def unfollow_tag(self, user_id: str, tag: str) -> List[str]:
        """Remove a tag from the user's followed tags. Returns updated list."""
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        tag = tag.strip().lower()[:64]
        user.followed_tags = [t for t in user.followed_tags if t != tag]
        return list(user.followed_tags)

    def get_followed_tags(self, user_id: str) -> List[str]:
        """Return the list of tags the user follows."""
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        return list(user.followed_tags)

    # --- User search ---

    def search_users(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        creator_verified: Optional[bool] = None,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search public user profiles by username or display_name (case-insensitive)."""
        q = query[:200].lower().strip()
        results = [
            u for u in self.store.list_users()
            if u.is_active and (not q or q in u.username.lower() or q in (u.display_name or "").lower())
        ]
        if creator_verified is not None:
            results = [u for u in results if u.is_creator_verified == creator_verified]
        if role is not None:
            results = [u for u in results if u.role == role]
        results.sort(key=lambda u: u.username.lower())
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
            "items": [u.public_profile() for u in page],
        }

    # --- User ban management ---

    def ban_user(self, admin_payload: Dict[str, Any], user_id: str, reason: str = "") -> UserRecord:
        """Ban a user account. Admin only."""
        self.require_role(admin_payload, "admin")
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        admin_id = admin_payload.get("sub", "")
        if user_id == admin_id:
            raise AuthError("forbidden", "自分自身を停止することはできません")
        user.is_banned = True
        user.ban_reason = reason.strip()[:500]
        user.banned_at = datetime.now(timezone.utc)
        user.banned_by = admin_id
        logger.info("User banned: %s by admin: %s reason: %s", user_id, admin_id, reason)
        return user

    def unban_user(self, admin_payload: Dict[str, Any], user_id: str) -> UserRecord:
        """Lift a ban from a user account. Admin only."""
        self.require_role(admin_payload, "admin")
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        user.is_banned = False
        user.ban_reason = ""
        user.banned_at = None
        user.banned_by = ""
        logger.info("User unbanned: %s by admin: %s", user_id, admin_payload.get("sub", ""))
        return user

    def get_banned_users(self, admin_payload: Dict[str, Any], limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List all banned users. Admin only."""
        self.require_role(admin_payload, "admin")
        banned = [u for u in self.store.list_users() if u.is_banned]
        banned.sort(key=lambda u: u.banned_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        total = len(banned)
        offset, limit = normalize_pagination(offset, limit)
        page = banned[offset: offset + limit]
        has_more = offset + limit < total
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "items": [
                {
                    **u.public_profile(),
                    "is_banned": u.is_banned,
                    "ban_reason": u.ban_reason,
                    "banned_at": u.banned_at.isoformat() if u.banned_at else None,
                    "banned_by": u.banned_by,
                }
                for u in page
            ],
        }

    # --- API key management ---

    def create_api_key(self, user_id: str, name: str) -> Dict[str, Any]:
        """Create a named API key for the given user. Returns metadata + raw_key (shown once)."""
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        name = name.strip()[:64]
        if not name:
            raise ValueError("API キー名を入力してください")
        return self.store.create_api_key(user_id, name)

    def revoke_api_key(self, user_id: str, key_id: str) -> bool:
        return self.store.revoke_api_key(user_id, key_id)

    def list_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        return self.store.list_api_keys(user_id)

    def verify_api_key(self, raw_key: str) -> Optional[Dict[str, Any]]:
        return self.store.verify_api_key(raw_key)

    # --- Helpers ---

    def change_password(self, user_id: str, current_password: str, new_password: str) -> None:
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        if not verify_password(current_password, user.password_hash):
            raise AuthError("invalid_credentials", "現在のパスワードが正しくありません")
        self._validate_password_strength(new_password)
        user.password_hash = hash_password(new_password)
        logger.info("Password changed for user_id: %s", user_id)

    @staticmethod
    def _validate_password_strength(password: str) -> None:
        if len(password) < 8:
            raise ValueError("パスワードは8文字以上必要です")
        if not any(c.isdigit() for c in password):
            raise ValueError("パスワードには数字を含めてください")
        if not any(c.isalpha() for c in password):
            raise ValueError("パスワードには文字を含めてください")


class AuthError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
_auth_manager: Optional[AuthManager] = None
_am_lock = __import__("threading").Lock()


def get_auth_manager() -> AuthManager:
    global _auth_manager
    if _auth_manager is None:
        with _am_lock:
            if _auth_manager is None:
                _auth_manager = AuthManager()
                # Warn loudly if the JWT signing secret was not set explicitly.
                # The module falls back to a random per-process secret, which is
                # secure but invalidates all tokens on restart and cannot be
                # shared across worker processes — production must set it.
                if not os.getenv("COCOA_JWT_SECRET"):
                    logger.warning(
                        "COCOA_JWT_SECRET is not set — using a random per-process "
                        "secret. Tokens will not survive restarts or work across "
                        "workers. Set COCOA_JWT_SECRET in production."
                    )
                # Seed a default admin for dev. Never ship a known constant
                # password: if COCOA_ADMIN_PASSWORD is unset, generate a random
                # one and log it once so a local dev can read it, rather than
                # exposing the well-known "admin/Admin1234!" default-credentials.
                if os.getenv("COCOA_CREATE_DEFAULT_ADMIN", "true").lower() == "true":
                    configured_pw = os.getenv("COCOA_ADMIN_PASSWORD")
                    admin_password = configured_pw or (secrets.token_urlsafe(16) + "A1!")
                    try:
                        _auth_manager.register("admin", "admin@cocoa.local", admin_password, role="admin")
                        if configured_pw:
                            logger.info("Default admin account created from COCOA_ADMIN_PASSWORD")
                        else:
                            logger.warning(
                                "Default admin account created with a RANDOM password "
                                "(set COCOA_ADMIN_PASSWORD to choose one): %s",
                                admin_password,
                            )
                    except ValueError:
                        pass  # Already exists
    return _auth_manager
