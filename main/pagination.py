"""Shared pagination helper enforcing a uniform, safe list-response contract.

Every list endpoint in Cocoa returns the same shape:

    {total, offset, limit, has_more, next_offset, items}

and must clamp client-supplied offset/limit so malformed or hostile values
cannot:
  - return the wrong page (negative offset → Python negative slicing),
  - loop a paging client forever (limit <= 0 yields an empty page that still
    reports has_more with an unchanged next_offset), or
  - exhaust memory/bandwidth (limit set absurdly high returns the whole table).

Use ``normalize_pagination`` to clamp raw inputs, or ``paginate`` to clamp,
slice, and build the full contract dict in one call.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def normalize_pagination(
    offset: Any, limit: Any, *, max_limit: int = MAX_LIMIT
) -> Tuple[int, int]:
    """Clamp (offset, limit) to safe bounds.

    offset → non-negative int (negative or non-numeric becomes 0).
    limit  → int in [1, max_limit]; non-positive or non-numeric becomes
             DEFAULT_LIMIT, anything above max_limit is capped.
    """
    try:
        offset = int(offset)
    except (TypeError, ValueError):
        offset = 0
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT

    if offset < 0:
        offset = 0
    if limit < 1:
        limit = DEFAULT_LIMIT
    if limit > max_limit:
        limit = max_limit
    return offset, limit


def paginate(
    items: Sequence[Any],
    offset: Any,
    limit: Any,
    *,
    max_limit: int = MAX_LIMIT,
    transform: Optional[Callable[[Any], Any]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Clamp, slice, and build the standard pagination contract dict.

    ``items`` is the full (already filtered/sorted) sequence.  ``transform``,
    if given, maps each item on the returned page (e.g. ``lambda x: x.to_dict()``).
    Any ``extra`` keyword pairs are merged into the result (e.g. ``query=...``).
    """
    offset, limit = normalize_pagination(offset, limit, max_limit=max_limit)
    total = len(items)
    page: List[Any] = list(items[offset: offset + limit])
    if transform is not None:
        page = [transform(x) for x in page]
    has_more = offset + limit < total
    result: Dict[str, Any] = {
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": has_more,
        "next_offset": offset + limit if has_more else None,
        "items": page,
    }
    if extra:
        result.update(extra)
    return result
