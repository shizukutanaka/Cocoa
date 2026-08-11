"""Cocoa SecurityManager — application-level security primitives.

This module backs ``tests/test_security.py``. It deliberately stays
self-contained (stdlib + optional bcrypt/cryptography) so security checks
work even in a minimal CI environment.

Provided capabilities
---------------------
* password hashing / verification and password-policy validation
* session lifecycle with IP binding, CSRF tokens and zero-trust access checks
* symmetric encryption / decryption of small secrets
* input-threat detection (SQL injection, XSS)
* upload scanning (extension allowlist + magic-number sniffing)
* a security-event audit trail and an aggregate self-audit report

Note: ``integrated_security.py`` holds the heavier platform/ML-flavoured
security stack. This module is the lightweight, synchronous surface used by
the app's auth/session/upload paths.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

try:  # optional, strongly preferred for password hashing
    import bcrypt
except Exception:  # pragma: no cover - exercised only without bcrypt
    bcrypt = None

try:  # optional, preferred for data encryption
    from cryptography.fernet import Fernet
except Exception:  # pragma: no cover
    Fernet = None


# ---------------------------------------------------------------------------
# Enums / records
# ---------------------------------------------------------------------------
class ThreatLevel(Enum):
    """Severity of a recorded security event."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityEventRecord:
    """One entry of the audit trail."""

    event_type: str
    severity: ThreatLevel
    source_ip: str = ""
    user: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "severity": self.severity.name,
            "source_ip": self.source_ip,
            "user": self.user,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PasswordPolicy:
    min_length: int = 8
    require_upper: bool = True
    require_lower: bool = True
    require_digit: bool = True
    require_symbol: bool = True
    # Reject passwords containing the username (case-insensitive).
    forbid_username: bool = True


# Substrings that make a password trivially guessable.
_COMMON_PASSWORDS = {
    "password", "123456", "12345678", "qwerty", "abc123",
    "letmein", "admin", "welcome", "iloveyou", "monkey",
}

_SQLI_PATTERNS = [
    r"(?i)'\s*(or|and)\s+'?\d+'?\s*=\s*'?\d+",       # ' OR '1'='1
    r"(?i)(^|\s|;)\s*(drop|truncate|alter)\s+table\b",
    r"(?i);\s*(drop|delete|update|insert|truncate)\b",  # stacked query
    r"(?i)\bunion\s+(all\s+)?select\b",
    r"(?i)--\s*$",                                     # trailing comment
    r"(?i)/\*.*?\*/",                                  # inline comment
    r"(?i)\b(exec|execute)\s*\(",
    r"(?i)\bxp_cmdshell\b",
    r"(?i)'\s*;\s*",                                   # quote-terminated stmt
]

_XSS_PATTERNS = [
    r"(?i)<\s*script\b",
    r"(?i)<\s*/\s*script\s*>",
    r"(?i)<\s*iframe\b",
    r"(?i)<\s*object\b",
    r"(?i)<\s*embed\b",
    r"(?i)javascript\s*:",
    r"(?i)\bon(error|load|click|mouseover|focus|submit)\s*=",
    r"(?i)<\s*img\b[^>]*\bsrc\s*=\s*['\"]?\s*javascript:",
    r"(?i)document\.(cookie|write)\b",
    r"(?i)\beval\s*\(",
]

# Upload allowlist.
_ALLOWED_UPLOAD_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv", ".log",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
    ".mp4", ".webm", ".mp3", ".wav", ".ogg",
    ".pdf", ".zip", ".vrm", ".fbx", ".glb", ".gltf",
}

_BLOCKED_UPLOAD_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bat", ".cmd", ".com", ".scr",
    ".msi", ".sh", ".ps1", ".vbs", ".js", ".jar", ".py", ".php",
}

# Magic numbers of executable / dangerous formats, checked regardless of
# the declared extension so a renamed .exe is still rejected.
_DANGEROUS_MAGIC: List[Tuple[bytes, str]] = [
    (b"MZ", "Windows executable (PE/MZ header)"),
    (b"\x7fELF", "Linux executable (ELF header)"),
    (b"\xca\xfe\xba\xbe", "Mach-O / Java class binary"),
    (b"\xfe\xed\xfa\xce", "Mach-O executable"),
    (b"#!", "script with shebang"),
]

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MiB


class SecurityManager:
    """Synchronous security helper for auth, sessions, input and uploads."""

    # Exposed as an attribute so callers (and tests) can do
    # ``sm.ThreatLevel.MEDIUM`` without a second import.
    ThreatLevel = ThreatLevel

    def __init__(
        self,
        password_policy: Optional[PasswordPolicy] = None,
        session_timeout_seconds: int = 3600,
        rate_limit_max: int = 60,
        rate_limit_window_seconds: int = 60,
        encryption_key: Optional[bytes] = None,
        max_security_events: int = 10_000,
    ) -> None:
        self.password_policy = password_policy or PasswordPolicy()
        self.session_timeout = session_timeout_seconds
        self.rate_limit_max = rate_limit_max
        self.rate_limit_window = rate_limit_window_seconds
        self.max_security_events = max_security_events

        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.security_events: List[SecurityEventRecord] = []
        self._rate_buckets: Dict[str, List[float]] = {}
        self.zero_trust_enabled = False
        self._lock = threading.RLock()

        self._fernet = None
        if Fernet is not None:
            key = encryption_key or os.environ.get("COCOA_ENCRYPTION_KEY")
            if isinstance(key, str):
                key = key.encode()
            if not key:
                key = Fernet.generate_key()
            else:
                # Accept an arbitrary secret by deriving a valid Fernet key.
                try:
                    Fernet(key)
                except Exception:
                    key = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
            self._fernet = Fernet(key)
            self._enc_key = key
        else:  # pragma: no cover - only without cryptography
            self._enc_key = (
                encryption_key
                or os.environ.get("COCOA_ENCRYPTION_KEY", "").encode()
                or secrets.token_bytes(32)
            )

    # ------------------------------------------------------------------
    # Passwords
    # ------------------------------------------------------------------
    def hash_password(self, password: str) -> str:
        """Hash *password* with bcrypt (PBKDF2-SHA256 fallback)."""
        if not isinstance(password, str) or not password:
            raise ValueError("password must be a non-empty string")
        if bcrypt is not None:
            return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
        salt = secrets.token_bytes(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
        return "pbkdf2_sha256$260000$%s$%s" % (
            base64.b64encode(salt).decode(),
            base64.b64encode(dk).decode(),
        )

    def verify_password(self, password: str, hashed: str) -> bool:
        """Constant-time verification of *password* against *hashed*."""
        if not password or not hashed:
            return False
        try:
            if hashed.startswith("pbkdf2_sha256$"):
                _, iters, salt_b64, dk_b64 = hashed.split("$")
                dk = hashlib.pbkdf2_hmac(
                    "sha256", password.encode("utf-8"),
                    base64.b64decode(salt_b64), int(iters),
                )
                return hmac.compare_digest(dk, base64.b64decode(dk_b64))
            if bcrypt is not None:
                return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except Exception as exc:
            logger.debug("Password verification failed: %s", exc)
        return False

    def validate_password(self, password: str, username: str = "") -> Tuple[bool, List[str]]:
        """Return ``(is_valid, errors)`` for *password* under the policy."""
        errors: List[str] = []
        p = self.password_policy
        if not isinstance(password, str):
            return False, ["パスワードは文字列である必要があります"]
        if len(password) < p.min_length:
            errors.append(f"パスワードは{p.min_length}文字以上である必要があります")
        if p.require_upper and not re.search(r"[A-Z]", password):
            errors.append("大文字を1文字以上含めてください")
        if p.require_lower and not re.search(r"[a-z]", password):
            errors.append("小文字を1文字以上含めてください")
        if p.require_digit and not re.search(r"\d", password):
            errors.append("数字を1文字以上含めてください")
        if p.require_symbol and not re.search(r"[^A-Za-z0-9]", password):
            errors.append("記号を1文字以上含めてください")
        if password.lower() in _COMMON_PASSWORDS:
            errors.append("よく使われるパスワードは使用できません")
        if p.forbid_username and username and username.lower() in password.lower():
            errors.append("パスワードにユーザー名を含めることはできません")
        return (not errors), errors

    # ------------------------------------------------------------------
    # Sessions / CSRF / zero trust
    # ------------------------------------------------------------------
    def create_session(self, username: str, ip_address: str) -> str:
        """Create a session bound to *username* and *ip_address*."""
        session_id = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            self.active_sessions[session_id] = {
                "username": username,
                "ip_address": ip_address,
                "created_at": now,
                "last_seen": now,
                "csrf_token": secrets.token_urlsafe(32),
            }
        self._log_security_event(
            "SESSION_CREATED", ThreatLevel.LOW, ip_address, username, {}
        )
        return session_id

    def validate_session(
        self, session_id: str, ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Validate a session. Returns ``(is_valid, session_info_or_None)``.

        A session is invalid when unknown, expired, or presented from an IP
        other than the one it was bound to (session hijacking defence).
        """
        with self._lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return False, None
            if time.time() - session["created_at"] > self.session_timeout:
                self.active_sessions.pop(session_id, None)
                self._log_security_event(
                    "SESSION_EXPIRED", ThreatLevel.LOW,
                    session["ip_address"], session["username"], {},
                )
                return False, None
            if ip_address is not None and ip_address != session["ip_address"]:
                self._log_security_event(
                    "SESSION_IP_MISMATCH", ThreatLevel.HIGH, ip_address,
                    session["username"], {"expected_ip": session["ip_address"]},
                )
                return False, None
            session["last_seen"] = time.time()
            return True, dict(session)

    def destroy_session(self, session_id: str) -> bool:
        with self._lock:
            session = self.active_sessions.pop(session_id, None)
        if session:
            self._log_security_event(
                "SESSION_DESTROYED", ThreatLevel.LOW,
                session["ip_address"], session["username"], {},
            )
        return session is not None

    def validate_csrf_token(self, session_id: str, token: str) -> bool:
        with self._lock:
            session = self.active_sessions.get(session_id)
        if not session or not token:
            return False
        ok = hmac.compare_digest(str(session["csrf_token"]), str(token))
        if not ok:
            self._log_security_event(
                "CSRF_TOKEN_INVALID", ThreatLevel.HIGH,
                session["ip_address"], session["username"], {},
            )
        return ok

    def enable_zero_trust(self) -> None:
        self.zero_trust_enabled = True
        self._log_security_event("ZERO_TRUST_ENABLED", ThreatLevel.LOW, "", "", {})

    def disable_zero_trust(self) -> None:
        self.zero_trust_enabled = False

    def validate_zero_trust_access(
        self, session_id: str, resource: str, action: str
    ) -> bool:
        """Per-request access check: every call re-validates the session.

        ``admin`` users may perform any action; other users get read access
        to non-admin resources only.
        """
        valid, session = self.validate_session(session_id)
        if not valid or session is None:
            self._log_security_event(
                "ACCESS_DENIED_INVALID_SESSION", ThreatLevel.MEDIUM, "", "",
                {"resource": resource, "action": action},
            )
            return False

        username = session["username"]
        if username == "admin":
            return True
        if resource.startswith("admin") and username != "admin":
            self._log_security_event(
                "ACCESS_DENIED_PRIVILEGE", ThreatLevel.HIGH,
                session["ip_address"], username,
                {"resource": resource, "action": action},
            )
            return False
        return action in ("read", "list")

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
    def check_rate_limit(self, identifier: str) -> Tuple[bool, int]:
        """Sliding-window limiter. Returns ``(allowed, remaining)``."""
        now = time.time()
        with self._lock:
            bucket = [t for t in self._rate_buckets.get(identifier, [])
                      if now - t < self.rate_limit_window]
            if len(bucket) >= self.rate_limit_max:
                self._rate_buckets[identifier] = bucket
                self._log_security_event(
                    "RATE_LIMIT_EXCEEDED", ThreatLevel.MEDIUM, "", identifier, {},
                )
                return False, 0
            bucket.append(now)
            self._rate_buckets[identifier] = bucket
            return True, self.rate_limit_max - len(bucket)

    # ------------------------------------------------------------------
    # Encryption
    # ------------------------------------------------------------------
    def encrypt_data(self, data: Union[str, bytes]) -> str:
        raw = data.encode("utf-8") if isinstance(data, str) else data
        if self._fernet is not None:
            return self._fernet.encrypt(raw).decode("ascii")
        # Fallback: HMAC-authenticated XOR keystream (no cryptography pkg).
        nonce = secrets.token_bytes(16)
        stream = self._keystream(nonce, len(raw))
        ct = bytes(a ^ b for a, b in zip(raw, stream))
        tag = hmac.new(self._enc_key, nonce + ct, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(nonce + ct + tag).decode("ascii")

    def decrypt_data(self, token: Union[str, bytes]) -> str:
        if self._fernet is not None:
            raw = token.encode("ascii") if isinstance(token, str) else token
            return self._fernet.decrypt(raw).decode("utf-8")
        blob = base64.urlsafe_b64decode(token)
        nonce, ct, tag = blob[:16], blob[16:-32], blob[-32:]
        expected = hmac.new(self._enc_key, nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected):
            raise ValueError("encrypted payload failed integrity check")
        stream = self._keystream(nonce, len(ct))
        return bytes(a ^ b for a, b in zip(ct, stream)).decode("utf-8")

    def _keystream(self, nonce: bytes, length: int) -> bytes:  # pragma: no cover
        out = b""
        counter = 0
        while len(out) < length:
            out += hashlib.sha256(
                self._enc_key + nonce + counter.to_bytes(8, "big")
            ).digest()
            counter += 1
        return out[:length]

    # ------------------------------------------------------------------
    # Input threat detection
    # ------------------------------------------------------------------
    def detect_sql_injection(self, value: str) -> bool:
        """True when *value* looks like an SQL-injection payload.

        A plain parameterised-looking query string is NOT flagged; the
        patterns target quote-breaking, stacked statements, comment
        terminators and UNION-based extraction.
        """
        if not isinstance(value, str) or not value:
            return False
        for pattern in _SQLI_PATTERNS:
            if re.search(pattern, value):
                self._log_security_event(
                    "SQL_INJECTION_DETECTED", ThreatLevel.CRITICAL, "", "",
                    {"pattern": pattern, "sample": value[:120]},
                )
                return True
        return False

    def detect_xss(self, value: str) -> bool:
        """True when *value* contains an XSS payload."""
        if not isinstance(value, str) or not value:
            return False
        for pattern in _XSS_PATTERNS:
            if re.search(pattern, value):
                self._log_security_event(
                    "XSS_DETECTED", ThreatLevel.HIGH, "", "",
                    {"pattern": pattern, "sample": value[:120]},
                )
                return True
        return False

    def sanitize_input(self, value: str) -> str:
        """Escape HTML-significant characters for safe rendering."""
        if not isinstance(value, str):
            return ""
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )

    # ------------------------------------------------------------------
    # Uploads
    # ------------------------------------------------------------------
    def scan_file_upload(
        self, file_path: Union[str, Path], content: bytes
    ) -> Tuple[bool, List[str]]:
        """Validate an upload. Returns ``(is_allowed, issues)``.

        Both the declared extension AND the actual byte signature are
        checked, so renaming ``payload.exe`` to ``avatar.png`` is still
        rejected.
        """
        issues: List[str] = []
        path = Path(file_path)
        ext = path.suffix.lower()

        if not content:
            issues.append("空のファイルはアップロードできません")
        if len(content) > _MAX_UPLOAD_BYTES:
            issues.append(
                f"ファイルサイズが上限({_MAX_UPLOAD_BYTES // (1024 * 1024)}MB)を超えています"
            )
        if ext in _BLOCKED_UPLOAD_EXTENSIONS:
            issues.append(f"許可されていない拡張子です: {ext}")
        elif ext not in _ALLOWED_UPLOAD_EXTENSIONS:
            issues.append(f"未対応の拡張子です: {ext or '(なし)'}")

        for magic, label in _DANGEROUS_MAGIC:
            if content.startswith(magic):
                issues.append(f"実行可能ファイルの内容が検出されました: {label}")
                break

        # Path traversal / NUL byte in the supplied name.
        name = str(file_path)
        if ".." in name or "\x00" in name:
            issues.append("不正なファイルパスです")

        if issues:
            self._log_security_event(
                "UPLOAD_REJECTED", ThreatLevel.HIGH, "", "",
                {"filename": path.name, "issues": issues},
            )
            return False, issues
        return True, []

    # ------------------------------------------------------------------
    # Audit trail
    # ------------------------------------------------------------------
    def _log_security_event(
        self,
        event_type: str,
        severity: ThreatLevel = ThreatLevel.LOW,
        source_ip: str = "",
        user: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> SecurityEventRecord:
        event = SecurityEventRecord(
            event_type=event_type,
            severity=severity,
            source_ip=source_ip,
            user=user,
            details=details or {},
        )
        with self._lock:
            self.security_events.append(event)
            if len(self.security_events) > self.max_security_events:
                # Keep the newest half; the trail is advisory, not the system
                # of record, and must not grow without bound.
                self.security_events = self.security_events[-(self.max_security_events // 2):]
        if severity in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
            logger.warning("Security event: %s (%s)", event_type, severity.name)
        return event

    def get_security_events(
        self, event_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        with self._lock:
            events = list(self.security_events)
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return [e.to_dict() for e in events[-limit:]]

    def perform_security_audit(self) -> Dict[str, Any]:
        """Aggregate self-audit of the current security posture."""
        with self._lock:
            events = list(self.security_events)
            sessions = dict(self.active_sessions)

        by_severity: Dict[str, int] = {}
        for e in events:
            by_severity[e.severity.name] = by_severity.get(e.severity.name, 0) + 1

        p = self.password_policy
        policy_compliance = {
            "password_min_length_ok": p.min_length >= 8,
            "password_complexity_ok": all(
                [p.require_upper, p.require_lower, p.require_digit, p.require_symbol]
            ),
            "zero_trust_enabled": self.zero_trust_enabled,
            "session_timeout_ok": self.session_timeout <= 3600,
            "encryption_available": self._fernet is not None,
            "bcrypt_available": bcrypt is not None,
        }

        vulnerabilities: List[Dict[str, str]] = []
        recommendations: List[str] = []

        if not policy_compliance["password_min_length_ok"]:
            vulnerabilities.append({
                "id": "WEAK_PASSWORD_POLICY",
                "severity": ThreatLevel.HIGH.name,
                "description": "パスワード最小長が8文字未満です",
            })
            recommendations.append("パスワード最小長を8文字以上に設定してください")
        if not policy_compliance["password_complexity_ok"]:
            recommendations.append("パスワードの複雑性要件をすべて有効にしてください")
        if not policy_compliance["zero_trust_enabled"]:
            recommendations.append("ゼロトラストアクセス制御の有効化を検討してください")
        if not policy_compliance["encryption_available"]:
            vulnerabilities.append({
                "id": "NO_CRYPTOGRAPHY_BACKEND",
                "severity": ThreatLevel.MEDIUM.name,
                "description": "cryptography が未インストールのためフォールバック暗号を使用中",
            })
            recommendations.append("cryptography パッケージをインストールしてください")
        if not policy_compliance["bcrypt_available"]:
            recommendations.append("bcrypt パッケージをインストールしてください")
        if not policy_compliance["session_timeout_ok"]:
            recommendations.append("セッションタイムアウトを1時間以内に短縮してください")

        critical = by_severity.get(ThreatLevel.CRITICAL.name, 0)
        if critical:
            vulnerabilities.append({
                "id": "CRITICAL_EVENTS_RECORDED",
                "severity": ThreatLevel.CRITICAL.name,
                "description": f"重大なセキュリティイベントが{critical}件記録されています",
            })
            recommendations.append("重大イベントの監査ログを確認してください")

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "policy_compliance": policy_compliance,
            "vulnerabilities": vulnerabilities,
            "recommendations": recommendations,
            "event_counts": by_severity,
            "total_events": len(events),
            "active_sessions": len(sessions),
        }


_default_manager: Optional[SecurityManager] = None
_default_lock = threading.Lock()


def get_security_manager() -> SecurityManager:
    """Process-wide singleton accessor."""
    global _default_manager
    with _default_lock:
        if _default_manager is None:
            _default_manager = SecurityManager()
        return _default_manager


__all__ = [
    "SecurityManager",
    "SecurityEventRecord",
    "PasswordPolicy",
    "ThreatLevel",
    "get_security_manager",
]
