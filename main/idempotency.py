"""Server-side idempotency for financial mutations.

Networks retry: a client whose request succeeded but whose response was lost
will resend the identical request, double-charging on a financial mutation
(gift-card purchase, tip, ...).  An ``IdempotencyStore`` lets a handler run a
side-effecting operation at most once per (caller, key): the first call with a
given key executes and caches the result; any retry with the same key replays
the cached result without re-executing.

Usage::

    store = get_idempotency_store()
    result = store.get_or_execute(f"{user_id}:{idem_key}", lambda: do_purchase())

Concurrent requests with the same key are serialized so only one executes.
The store is bounded (max entries + TTL) so it cannot grow without bound.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional

_DEFAULT_MAX_ENTRIES = 10_000
_DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24h

_MISSING = object()  # sentinel distinguishing "not cached" from "cached None"


class IdempotencyStore:
    """Thread-safe at-most-once execution cache keyed by an idempotency key."""

    def __init__(
        self,
        max_entries: int = _DEFAULT_MAX_ENTRIES,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._results: "OrderedDict[str, tuple]" = OrderedDict()  # key -> (result, stored_at)
        # Per-key locks are reference-counted by in-flight operations. The lock
        # object MUST stay stable for the whole duration of every get_or_execute
        # call on that key: if it were swapped out (e.g. dropped on TTL expiry
        # while a caller holds it), a concurrent retry would create a *different*
        # lock and both callers would execute fn — a double-charge. So a key's
        # lock is removed only when no operation references it any more, never
        # because its cached result expired or was evicted.
        self._key_locks: Dict[str, threading.Lock] = {}
        self._key_refcount: Dict[str, int] = {}

    # -- internal helpers (call under self._lock) --------------------------

    def _get_locked(self, key: str) -> Any:
        """Return the cached result or ``_MISSING`` if absent/expired."""
        entry = self._results.get(key)
        if entry is None:
            return _MISSING
        result, stored_at = entry
        if time.time() - stored_at > self._ttl:
            # Drop only the RESULT — never the key lock, which a caller may be
            # holding right now (removing it would break same-key exclusion).
            self._results.pop(key, None)
            return _MISSING
        self._results.move_to_end(key)  # LRU touch
        return result

    def _put_locked(self, key: str, result: Any) -> None:
        self._results[key] = (result, time.time())
        self._results.move_to_end(key)
        # Bound the result cache. Key locks are NOT touched here — their lifetime
        # is governed by the in-flight refcount, not by result eviction.
        while len(self._results) > self._max_entries:
            self._results.popitem(last=False)

    def _acquire_key_lock(self, key: str) -> threading.Lock:
        """Return the shared lock for ``key`` and register an in-flight reference
        so it can't be removed while this operation runs."""
        with self._lock:
            lk = self._key_locks.get(key)
            if lk is None:
                lk = threading.Lock()
                self._key_locks[key] = lk
            self._key_refcount[key] = self._key_refcount.get(key, 0) + 1
            return lk

    def _release_key_lock(self, key: str) -> None:
        """Drop one in-flight reference; remove the lock once none remain."""
        with self._lock:
            n = self._key_refcount.get(key, 0) - 1
            if n <= 0:
                self._key_refcount.pop(key, None)
                self._key_locks.pop(key, None)
            else:
                self._key_refcount[key] = n

    # -- public API --------------------------------------------------------

    def get_or_execute(self, key: Optional[str], fn: Callable[[], Any]) -> Any:
        """Run ``fn`` at most once per non-empty ``key`` and cache its result.

        With a falsy key, idempotency is not requested and ``fn`` always runs
        (no caching).  Same-key calls are serialized so a retry that races the
        original still executes exactly once.
        """
        if not key:
            return fn()
        per_key = self._acquire_key_lock(key)
        try:
            with per_key:
                with self._lock:
                    cached = self._get_locked(key)
                if cached is not _MISSING:
                    return cached
                result = fn()
                with self._lock:
                    self._put_locked(key, result)
                return result
        finally:
            self._release_key_lock(key)

    def seen(self, key: str) -> bool:
        """Return True if a (non-expired) result is cached for ``key``."""
        with self._lock:
            return self._get_locked(key) is not _MISSING

    def size(self) -> int:
        with self._lock:
            return len(self._results)


_store: Optional[IdempotencyStore] = None
_store_lock = threading.Lock()


def get_idempotency_store() -> IdempotencyStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = IdempotencyStore()
    return _store
