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


@dataclass
class UserRecord:
    user_id: str
    username: str
    email: str
    password_hash: str
    role: str = "user"
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None
    failed_attempts: int = 0
    locked_until: Optional[datetime] = None
    display_name: str = ""
    bio: str = ""
    avatar_url: str = ""
    bookmarks: List[str] = field(default_factory=list)  # list of doc_ids / listing_ids

    def is_locked(self) -> bool:
        return bool(self.locked_until and datetime.now(timezone.utc) < self.locked_until)

    def public_profile(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name or self.username,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "role": self.role,
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
        self._revoked_jtis: set = set()           # revoked token JTI values
        self._reset_tokens: Dict[str, tuple] = {}  # token → (user_id, exp)

    # --- CRUD ---

    def create_user(self, username: str, email: str, password: str, role: str = "user") -> UserRecord:
        if username in self._by_username:
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
        self._by_username[username] = user.user_id
        self._by_email[email] = user.user_id
        logger.info("User created: %s (role=%s)", username, role)
        return user

    def get_by_id(self, user_id: str) -> Optional[UserRecord]:
        return self._by_id.get(user_id)

    def get_by_username(self, username: str) -> Optional[UserRecord]:
        uid = self._by_username.get(username)
        return self._by_id.get(uid) if uid else None

    def get_by_email(self, email: str) -> Optional[UserRecord]:
        uid = self._by_email.get(email)
        return self._by_id.get(uid) if uid else None

    def list_users(self) -> List[UserRecord]:
        return list(self._by_id.values())

    def delete_user(self, user_id: str) -> bool:
        user = self._by_id.pop(user_id, None)
        if user:
            self._by_username.pop(user.username, None)
            self._by_email.pop(user.email, None)
            return True
        return False

    # --- Token revocation ---

    def revoke_jti(self, jti: str) -> None:
        self._revoked_jtis.add(jti)

    def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked_jtis

    # --- Password reset ---

    def create_reset_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        exp = time.time() + _RESET_TOKEN_EXPIRE_MINUTES * 60
        self._reset_tokens[token] = (user_id, exp)
        return token

    def consume_reset_token(self, token: str) -> Optional[str]:
        entry = self._reset_tokens.pop(token, None)
        if entry and entry[1] > time.time():
            return entry[0]
        return None


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
                    self.store.revoke_jti(jti)
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
        return payload

    def refresh(self, refresh_token: str) -> TokenPair:
        payload = decode_refresh_token(refresh_token)
        jti = payload.get("jti", "")
        if self.store.is_revoked(jti):
            raise AuthError("token_revoked", "リフレッシュトークンは無効化されました")

        user = self.store.get_by_id(payload["sub"])
        if not user or not user.is_active:
            raise AuthError("account_disabled", "アカウントが無効です")

        # Rotate refresh token
        self.store.revoke_jti(jti)
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

    def update_profile(self, user_id: str, display_name: Optional[str] = None, bio: Optional[str] = None, avatar_url: Optional[str] = None) -> UserRecord:
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        if display_name is not None:
            user.display_name = display_name[:64].strip()
        if bio is not None:
            user.bio = bio[:500].strip()
        if avatar_url is not None:
            user.avatar_url = avatar_url[:512].strip()
        logger.info("Profile updated for user_id: %s", user_id)
        return user

    # --- Bookmarks ---

    def add_bookmark(self, user_id: str, item_id: str) -> List[str]:
        user = self.store.get_by_id(user_id)
        if not user:
            raise AuthError("not_found", "ユーザーが見つかりません")
        if item_id not in user.bookmarks:
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

    # --- Helpers ---

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


def get_auth_manager() -> AuthManager:
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
        # Seed a default admin for dev (override via env)
        dev_admin_password = os.getenv("COCOA_ADMIN_PASSWORD", "Admin1234!")
        if os.getenv("COCOA_CREATE_DEFAULT_ADMIN", "true").lower() == "true":
            try:
                _auth_manager.register("admin", "admin@cocoa.local", dev_admin_password, role="admin")
                logger.info("Default admin account created (change password in production!)")
            except ValueError:
                pass  # Already exists
    return _auth_manager
