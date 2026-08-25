"""Whole-store durability: save every in-memory store to one JSON file.

FEATURE_AUDIT §3-4 recorded that all business state lives in process memory, so
a restart or deploy wipes it. #71 made the minimal coherent unit durable
(accounts + credit balances) using each store's own hand-written persistence
API. This module generalises that to every store without hand-writing a
serializer per class: `state_codec` round-trips the live objects exactly, so a
store's whole ``vars()`` can be captured and restored.

Design notes
------------
* One file, one moment. Splitting stores across files invites restoring a cart
  from 10:00 against listings from 10:05; a single atomic write cannot tear.
* The caller supplies the store objects, so this module imports no subsystems
  and stays trivially testable.
* Fail closed. A snapshot that cannot be decoded raises rather than letting the
  server open with silently missing data -- the money version of the #47
  "empty result vs outage" anti-pattern.
* Derived state is not saved: the search index rebuilds from listings, and
  idempotency/rate-limit/cache entries are short-lived by definition.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from typing import Any, Dict, Optional, Type

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None  # type: ignore

# Relative-first, flat fallback: the canonical runtime imports this as
# main.state_snapshot, but the test suite puts main/ on sys.path and imports it
# flat. Getting this wrong is the packaging trap documented in
# HANDOFF_INSTRUCTIONS §1.1 (it caused two production 503s).
try:
    from .state_codec import build_registry, restore_attrs, snapshot_attrs
except ImportError:  # pragma: no cover - flat layout
    from state_codec import build_registry, restore_attrs, snapshot_attrs

logger = logging.getLogger(__name__)

SNAPSHOT_VERSION = 1
SNAPSHOT_FILENAME = "state.json"

# Attributes that are configuration or injected behaviour rather than data.
# Restoring them would overwrite the live process's settings with whatever the
# snapshot happened to be written with.
# Only CONFIGURATION is excluded -- values a deployment reads from its
# environment at boot. Restoring those would let a stale snapshot silently
# override the live settings.
#
# Nothing security-relevant is excluded, and that is deliberate. An earlier
# revision skipped the auth store's revoked-token list, reset tokens and API
# keys as "transient". Persisting accounts while dropping revocations turned
# out to be a security regression: with a stable COCOA_JWT_SECRET a token
# issued before a restart is still cryptographically valid afterwards, so a
# token that had been explicitly revoked by logout came back to life. Before
# durability existed a restart wiped every account, so no token could resolve
# to anyone -- persistence is what made it exploitable (the same way it turned
# the #73 admin demotion into a permanent lockout).
_SKIP_BY_STORE: Dict[str, tuple] = {
    "notifications": ("_max",),
    "saved_searches": ("_max_per_user",),
}


def _registry_for(stores: Dict[str, Any]) -> Dict[str, Type]:
    """Every dataclass defined in the modules the stores come from."""
    modules = []
    for store in stores.values():
        module = sys.modules.get(type(store).__module__)
        if module is not None and module not in modules:
            modules.append(module)
    return build_registry(*modules)


def save(path: str, stores: Dict[str, Any]) -> Dict[str, Any]:
    """Atomically write every store to `path`. Returns a per-store field count."""
    payload: Dict[str, Any] = {"version": SNAPSHOT_VERSION, "stores": {}}
    counts: Dict[str, Any] = {}
    for key, store in stores.items():
        data = snapshot_attrs(store, skip=_SKIP_BY_STORE.get(key, ()))
        payload["stores"][key] = data
        counts[key] = len(data)

    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # atomic on POSIX; keeps mkstemp's 0600 mode
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return counts


def load(path: str, stores: Dict[str, Any]) -> Dict[str, Any]:
    """Restore stores from `path`.

    Returns ``{"loaded": False}`` when the file is absent (first run) so callers
    can load blindly at startup. A snapshot that exists but cannot be read is an
    error, never a silent empty start.
    """
    if not os.path.exists(path):
        return {"loaded": False, "restored": {}}
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict) or "stores" not in payload:
        raise ValueError("invalid snapshot: missing 'stores'")
    version = payload.get("version")
    if version != SNAPSHOT_VERSION:
        raise ValueError(
            f"snapshot version {version!r} is not supported by this build "
            f"(expected {SNAPSHOT_VERSION})"
        )
    registry = _registry_for(stores)
    restored: Dict[str, int] = {}
    for key, data in payload["stores"].items():
        store = stores.get(key)
        if store is None:
            # A store present in the snapshot but not in this deployment (a
            # subsystem that failed to import). Skipping is right -- there is
            # nothing to restore into -- but it must be visible.
            logger.warning("Snapshot contains state for absent subsystem %r; skipped", key)
            continue
        restore_attrs(store, data, registry)
        restored[key] = len(data)
    return {"loaded": True, "restored": restored}


# ---------------------------------------------------------------------------
# Single-writer enforcement
# ---------------------------------------------------------------------------
# The stores are per-process dictionaries, so running more than one worker
# against one state directory is not "slower but fine" -- it is silent
# destruction. Measured with `uvicorn --workers 2`: of 12 accounts registered
# through the API, only 3 could log in immediately, because each account lived
# in exactly one worker's memory while logins landed on whichever worker
# answered. Add durability and it gets worse: every worker autosaves the whole
# store over the same file, so the last writer erases the others' work.
#
# `--workers N` is the ordinary production invocation for uvicorn/gunicorn, and
# nothing in the product stopped it. An advisory lock turns a silent
# data-destroying misconfiguration into a refusal to start -- the same
# fail-closed choice already made for corrupt snapshots.

LOCK_FILENAME = ".state.lock"
_lock_handle = None


class StateDirInUseError(RuntimeError):
    """Another process already owns this state directory."""


def acquire_single_writer_lock(state_dir: str):
    """Take an exclusive advisory lock on `state_dir`.

    Returns the held file descriptor (kept open for the process lifetime), or
    None where locking is unavailable. Raises StateDirInUseError if another
    live process holds it.
    """
    global _lock_handle
    if fcntl is None:  # pragma: no cover - non-POSIX
        logger.warning("File locking unavailable; cannot enforce a single writer")
        return None
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, LOCK_FILENAME)
    handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        os.close(handle)
        raise StateDirInUseError(
            f"another process is already using the state directory {state_dir}. "
            f"Cocoa keeps its stores in process memory, so exactly one worker "
            f"may own them: run a single process (drop --workers, or set it to "
            f"1). Running several splits accounts and orders across workers and "
            f"lets them overwrite each other's snapshots."
        ) from e
    os.truncate(handle, 0)
    os.write(handle, f"{os.getpid()}\n".encode())
    os.fsync(handle)
    _lock_handle = handle
    return handle


def release_single_writer_lock() -> None:
    """Release the lock, if held. Safe to call when it was never taken."""
    global _lock_handle
    if _lock_handle is None:
        return
    try:
        if fcntl is not None:
            fcntl.flock(_lock_handle, fcntl.LOCK_UN)
        os.close(_lock_handle)
    except OSError:  # pragma: no cover
        pass
    finally:
        _lock_handle = None
