"""
Rate Limiting for Cocoa API

Implements:
- Token bucket algorithm per IP and per user
- Sliding window counters for burst detection
- Configurable per-endpoint overrides
- Works as FastAPI middleware and standalone function
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_DEFAULT_RATE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
_AUTH_RATE = int(os.getenv("RATE_LIMIT_AUTH_PER_MINUTE", "10"))
_WINDOW_SECONDS = 60
_BURST_MULTIPLIER = 2  # allow burst up to 2x normal rate for <5 seconds


# ---------------------------------------------------------------------------
# Sliding window counter
# ---------------------------------------------------------------------------
class _SlidingWindow:
    """Thread-safe sliding window request counter."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: deque = deque()
        self._lock = threading.Lock()

    def is_allowed(self) -> Tuple[bool, int, int]:
        """
        Returns (allowed, remaining, retry_after_seconds).
        """
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            # Drop expired entries
            while self._requests and self._requests[0] < cutoff:
                self._requests.popleft()

            count = len(self._requests)
            if count >= self.max_requests:
                oldest = self._requests[0] if self._requests else now
                retry_after = int(oldest + self.window_seconds - now) + 1
                return False, 0, retry_after

            self._requests.append(now)
            remaining = self.max_requests - count - 1
            return True, remaining, 0

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()


# ---------------------------------------------------------------------------
# Per-endpoint rate config
# ---------------------------------------------------------------------------
@dataclass
class EndpointLimit:
    max_requests: int
    window_seconds: int = _WINDOW_SECONDS


_ENDPOINT_OVERRIDES: Dict[str, EndpointLimit] = {
    "/api/auth/login": EndpointLimit(_AUTH_RATE),
    "/api/auth/register": EndpointLimit(_AUTH_RATE),
    "/api/auth/reset-password": EndpointLimit(5),
    "/api/auth/refresh": EndpointLimit(30),
    "/ws/monitoring": EndpointLimit(5),  # WS upgrades per minute
    # Financial / abuse-prone endpoints get auth-tier limits so they cannot be
    # brute-forced or used as enumeration oracles at the generous default rate.
    "/api/gift-cards/lookup": EndpointLimit(_AUTH_RATE),   # unauth validity/amount oracle
    "/api/gift-cards/redeem": EndpointLimit(_AUTH_RATE),   # gift-card code brute-force
    "/api/gift-cards": EndpointLimit(_AUTH_RATE),          # purchase (moves credits)
    "/api/refunds": EndpointLimit(_AUTH_RATE),             # refund-request spam
}


# ---------------------------------------------------------------------------
# Rate limiter registry
# ---------------------------------------------------------------------------
class RateLimiter:
    """
    In-memory rate limiter keyed by (client_key, endpoint).
    client_key is typically IP or user_id.
    """

    def __init__(self):
        self._windows: Dict[str, _SlidingWindow] = {}
        self._lock = threading.Lock()
        self._cleanup_counter = 0

    def _get_window(self, key: str, max_requests: int, window_seconds: int) -> _SlidingWindow:
        with self._lock:
            if key not in self._windows:
                self._windows[key] = _SlidingWindow(max_requests, window_seconds)
            return self._windows[key]

    def check(
        self,
        client_key: str,
        endpoint: str = "/",
        *,
        max_requests: Optional[int] = None,
        window_seconds: int = _WINDOW_SECONDS,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed.

        Returns (allowed, headers_dict).
        headers_dict contains X-RateLimit-* values for the response.
        """
        override = _ENDPOINT_OVERRIDES.get(endpoint)
        effective_max = max_requests or (override.max_requests if override else _DEFAULT_RATE)
        effective_window = override.window_seconds if override else window_seconds

        window_key = f"{client_key}:{endpoint}"
        window = self._get_window(window_key, effective_max, effective_window)
        allowed, remaining, retry_after = window.is_allowed()

        headers = {
            "X-RateLimit-Limit": str(effective_max),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(int(time.time()) + effective_window),
        }
        if not allowed:
            headers["Retry-After"] = str(retry_after)
            logger.warning("Rate limit exceeded: key=%s endpoint=%s", client_key, endpoint)

        # Periodic cleanup of old entries (every 1000 checks)
        self._cleanup_counter += 1
        if self._cleanup_counter % 1000 == 0:
            self._evict_old_windows()

        return allowed, headers

    def _evict_old_windows(self) -> None:
        with self._lock:
            stale = [k for k, w in self._windows.items() if not w._requests]
            for k in stale:
                del self._windows[k]

    def reset_client(self, client_key: str) -> None:
        """Reset all windows for a given client (e.g., after unblock)."""
        with self._lock:
            stale = [k for k in self._windows if k.startswith(f"{client_key}:")]
            for k in stale:
                self._windows[k].reset()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active_windows": len(self._windows),
                "endpoint_overrides": {k: v.max_requests for k, v in _ENDPOINT_OVERRIDES.items()},
                "default_limit": _DEFAULT_RATE,
                "window_seconds": _WINDOW_SECONDS,
            }


# ---------------------------------------------------------------------------
# FastAPI middleware integration
# ---------------------------------------------------------------------------
def get_client_ip(request: Any) -> str:
    """Extract real client IP, respecting X-Forwarded-For."""
    forwarded_for = None
    if hasattr(request, "headers"):
        forwarded_for = request.headers.get("x-forwarded-for")
        if not forwarded_for:
            forwarded_for = request.headers.get("cf-connecting-ip")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if hasattr(request, "client") and request.client:
        return request.client.host
    return "unknown"


# Shared singleton
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def add_endpoint_limit(path: str, max_requests: int, window_seconds: int = _WINDOW_SECONDS) -> None:
    """Register a custom rate limit for an endpoint path."""
    _ENDPOINT_OVERRIDES[path] = EndpointLimit(max_requests, window_seconds)
