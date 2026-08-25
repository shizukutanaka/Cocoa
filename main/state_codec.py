"""Lossless JSON codec for the in-memory stores' live objects.

Why not to_dict()
-----------------
Every store already has ``to_dict()`` methods, but those are API-presentation
serializers and several are deliberately lossy -- ``MarketplaceListing.to_dict``
omits ``parameters`` (the actual product a buyer paid for) and ``rating_sum``.
Restoring from them would silently destroy data, which is why the full
persistence migration stayed deferred for so long. This codec serializes the
LIVE objects instead, so a round trip is exact.

Why not pickle
--------------
Pickle handles these shapes natively, but unpickling a file an attacker can
write is remote code execution, whereas a corrupt JSON snapshot is at worst bad
data. Decoding here can only ever construct dataclasses from an explicit
registry, so an unknown or hostile type name is refused rather than imported.
The snapshots also stay human-readable, which matters when an operator has to
inspect or repair one.

Encoding
--------
JSON-native values pass through unchanged. Everything else is tagged:

    {"__t__": "dt",  "v": "<isoformat>"}          datetime
    {"__t__": "set", "v": [...]}                  set
    {"__t__": "tup", "v": [...]}                  tuple
    {"__t__": "map", "v": [[key, value], ...]}    dict with non-string keys
    {"__t__": "dc",  "n": "Name", "v": {...}}     registered dataclass

Tuple keys (``_purchase_seller``), sets of tuples (``_refunded_purchases``),
tuples containing datetimes (``_download_log``) and nested dataclasses all
survive because the encoder recurses structurally rather than by declared type.
"""

from __future__ import annotations

import threading
from dataclasses import fields as dataclass_fields, is_dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, Type

TAG = "__t__"

# Attribute types that must never be snapshotted: a lock is process state, not
# data, and restoring one would hand every thread a fresh unheld lock.
_SKIP_ATTR_TYPES = (threading.Lock().__class__, threading.RLock().__class__, threading.Event)


class StateCodecError(ValueError):
    """A snapshot could not be encoded or decoded."""


def encode(value: Any) -> Any:
    """Recursively convert live objects into JSON-safe tagged structures."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        return {TAG: "dt", "v": value.isoformat()}
    if isinstance(value, set):
        # Sorted where possible so snapshots of identical state are identical
        # on disk (easier diffing); falls back to insertion order for mixed
        # types that do not compare.
        try:
            items = sorted(value)
        except TypeError:
            items = list(value)
        return {TAG: "set", "v": [encode(v) for v in items]}
    if isinstance(value, tuple):
        return {TAG: "tup", "v": [encode(v) for v in value]}
    if isinstance(value, list):
        return [encode(v) for v in value]
    if isinstance(value, dict):
        if all(isinstance(k, str) for k in value):
            return {k: encode(v) for k, v in value.items()}
        return {TAG: "map", "v": [[encode(k), encode(v)] for k, v in value.items()]}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            TAG: "dc",
            "n": type(value).__name__,
            "v": {f.name: encode(getattr(value, f.name)) for f in dataclass_fields(value)},
        }
    raise StateCodecError(f"cannot encode value of type {type(value).__name__}")


def decode(value: Any, registry: Dict[str, Type]) -> Any:
    """Rebuild live objects. Only dataclasses named in `registry` are allowed."""
    if isinstance(value, list):
        return [decode(v, registry) for v in value]
    if not isinstance(value, dict):
        return value
    tag = value.get(TAG)
    if tag is None:
        return {k: decode(v, registry) for k, v in value.items()}
    if tag == "dt":
        return datetime.fromisoformat(value["v"])
    if tag == "set":
        return {decode(v, registry) for v in value["v"]}
    if tag == "tup":
        return tuple(decode(v, registry) for v in value["v"])
    if tag == "map":
        return {decode(k, registry): decode(v, registry) for k, v in value["v"]}
    if tag == "dc":
        name = value.get("n")
        cls = registry.get(name)
        if cls is None:
            raise StateCodecError(f"snapshot names an unregistered type: {name!r}")
        known = {f.name for f in dataclass_fields(cls)}
        # Unknown keys are dropped and missing ones fall back to the field's
        # default, so a snapshot written before/after a field was added still
        # loads. A field added WITHOUT a default is the one case that fails,
        # loudly, which is correct: there is no value to invent.
        kwargs = {k: decode(v, registry) for k, v in value["v"].items() if k in known}
        try:
            return cls(**kwargs)
        except TypeError as e:
            raise StateCodecError(f"cannot rebuild {name}: {e}") from e
    raise StateCodecError(f"unknown type tag: {tag!r}")


def snapshot_attrs(store: Any, skip: Iterable[str] = ()) -> Dict[str, Any]:
    """Encode a store's data attributes, skipping locks and anything named in `skip`.

    Reading ``vars(store)`` rather than a hand-maintained field list means a new
    attribute is captured automatically; forgetting to add it here is the kind
    of silent data-loss bug this whole module exists to avoid.
    """
    skip = set(skip)
    out: Dict[str, Any] = {}
    for name, value in vars(store).items():
        if name in skip or isinstance(value, _SKIP_ATTR_TYPES):
            continue
        if callable(value) and not is_dataclass(value):
            continue  # injected callbacks (e.g. two-factor verifier hooks)
        out[name] = encode(value)
    return out


def restore_attrs(store: Any, data: Dict[str, Any], registry: Dict[str, Type]) -> None:
    """Decode and assign attributes onto a live store, in place."""
    for name, value in data.items():
        setattr(store, name, decode(value, registry))


def build_registry(*modules) -> Dict[str, Type]:
    """Collect every dataclass defined in the given modules, by class name."""
    registry: Dict[str, Type] = {}
    for module in modules:
        for attr in vars(module).values():
            if isinstance(attr, type) and is_dataclass(attr):
                registry[attr.__name__] = attr
    return registry
