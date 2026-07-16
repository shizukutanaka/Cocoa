# main/template_filters.py
"""
テンプレートの検証・ID安全化・フィルタ/検索（仕様: docs/SPEC_TEMPLATE_LIBRARY.md）

`template_library` から純粋ロジックを分離した依存なしモジュール（標準ライブラリのみ）。
特に `sanitize_template_id` はパストラバーサル（`template_id` がそのままファイル名に
使われる問題）を防ぐ。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")

AVATAR_REQUIRED = ("template_id", "name", "description", "category", "style")
VIDEO_REQUIRED = ("template_id", "name", "description", "category", "script_template")


def sanitize_template_id(template_id: Any) -> str:
    """template_id を検証し、安全ならそのまま返す。REQ-TL-01。

    パス区切り・`..`・制御文字を含むものは ValueError。ファイル名生成の前に通すこと。
    """
    if not isinstance(template_id, str) or not template_id.strip():
        raise ValueError("template_id must be a non-empty string")
    tid = template_id.strip()
    if tid in (".", ".."):
        raise ValueError(f"unsafe template_id: {template_id!r}")
    if any(c in tid for c in ("/", "\\", "\x00")) or ".." in tid:
        raise ValueError(f"unsafe template_id (path traversal): {template_id!r}")
    if not _SAFE_ID.match(tid):
        raise ValueError(f"template_id contains invalid characters: {template_id!r}")
    return tid


def _validate_template(data: Any, required) -> Dict[str, Any]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return {"valid": False, "errors": ["template must be a JSON object"]}

    for key in required:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"'{key}' must be a non-empty string")

    tags = data.get("tags")
    if tags is not None and (not isinstance(tags, list) or any(not isinstance(t, str) for t in tags)):
        errors.append("'tags' must be a list of strings")

    tid = data.get("template_id")
    if isinstance(tid, str) and tid.strip():
        try:
            sanitize_template_id(tid)
        except ValueError as exc:
            errors.append(str(exc))

    return {"valid": not errors, "errors": errors}


def validate_avatar_template(data: Any) -> Dict[str, Any]:
    """アバターテンプレートの形式検証。REQ-TL-02。"""
    return _validate_template(data, AVATAR_REQUIRED)


def validate_video_template(data: Any) -> Dict[str, Any]:
    """動画テンプレートの形式検証。REQ-TL-03。"""
    return _validate_template(data, VIDEO_REQUIRED)


def _get(item: Any, key: str, default=None):
    """dict / 属性持ちオブジェクトの両対応アクセサ。"""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def filter_templates(
    items: List[Any],
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    premium_only: bool = False,
) -> List[Any]:
    """カテゴリ/タグ(OR)/プレミアムでフィルタする純関数。REQ-TL-04。"""
    result = list(items)
    if category:
        result = [t for t in result if _get(t, "category") == category]
    if tags:
        result = [t for t in result if any(tag in (_get(t, "tags") or []) for tag in tags)]
    if premium_only:
        result = [t for t in result if _get(t, "is_premium", False)]
    return result


def search_templates(items: List[Any], query: str) -> List[Any]:
    """name/description/tags を横断検索し usage_count 降順で返す。REQ-TL-05。"""
    q = (query or "").lower()
    matched = []
    for t in items:
        tags = _get(t, "tags") or []
        haystack = f"{_get(t, 'name', '')} {_get(t, 'description', '')} {' '.join(tags)}".lower()
        if q in haystack:
            matched.append(t)
    return sorted(matched, key=lambda t: _get(t, "usage_count", 0), reverse=True)
