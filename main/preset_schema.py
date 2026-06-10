# main/preset_schema.py
"""
プリセットの形式スキーマ検証（仕様: docs/SPEC_PRESET_PARAMETERS.md REQ-PM-07 / REQ-PM-12）

`validate_and_repair_presets` は欠損キーの補完(修復)を行うが、形式の妥当性を体系的に
検証する機能が無かった。本モジュールは依存ライブラリ無し(標準ライブラリのみ)で、
プリセット構造の検証と、検証＋VRChat 同期予算解析を束ねた解析を提供する。
"""
from __future__ import annotations

from typing import Any, Dict, List

import vrchat_parameter_budget as vpb

# 受理する Expression Parameter 型（大小無視）
PARAMETER_TYPES = {"bool", "int", "float", "trigger"}


def _check_default_type(ptype: str, default: Any) -> bool:
    """default 値が型に整合するか（緩め: Int/Float は数値、Bool は真偽）。"""
    t = ptype.lower()
    if t == "bool":
        return isinstance(default, bool)
    if t == "int":
        return isinstance(default, int) and not isinstance(default, bool)
    if t == "float":
        return isinstance(default, (int, float)) and not isinstance(default, bool)
    # Trigger は default を持たない想定
    return True


def validate_preset_schema(preset: Any) -> Dict[str, Any]:
    """プリセットの形式を検証する。REQ-PM-07。

    返り値: {valid: bool, errors: list[str], warnings: list[str]}
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(preset, dict):
        return {"valid": False, "errors": ["preset must be a JSON object"], "warnings": []}

    name = preset.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("'name' must be a non-empty string")

    params = preset.get("parameters")
    if not isinstance(params, list):
        errors.append("'parameters' must be a list")
        return {"valid": not errors, "errors": errors, "warnings": warnings}

    seen_names: set = set()
    for i, p in enumerate(params):
        if not isinstance(p, dict):
            errors.append(f"parameters[{i}] must be an object")
            continue
        _validate_parameter(i, p, seen_names, errors, warnings)

    return {"valid": not errors, "errors": errors, "warnings": warnings}


def _validate_parameter(
    i: int,
    p: Dict[str, Any],
    seen_names: set,
    errors: List[str],
    warnings: List[str],
) -> None:
    pname = p.get("name")
    if not isinstance(pname, str) or not pname.strip():
        errors.append(f"parameters[{i}].name must be a non-empty string")
    else:
        if pname in seen_names:
            errors.append(f"duplicate parameter name '{pname}'")
        seen_names.add(pname)

    ptype = p.get("type")
    if not isinstance(ptype, str) or ptype.strip().lower() not in PARAMETER_TYPES:
        errors.append(f"parameters[{i}].type must be one of Bool/Int/Float/Trigger (got {ptype!r})")
        ptype = None

    synced = p.get("synced", True)
    if not isinstance(synced, bool):
        errors.append(f"parameters[{i}].synced must be a boolean")

    if ptype is not None and "default" in p and not _check_default_type(ptype, p["default"]):
        warnings.append(
            f"parameters[{i}] ('{pname}') default {p['default']!r} は型 {ptype} と不整合の可能性"
        )


def analyze_preset(preset: Any) -> Dict[str, Any]:
    """スキーマ検証と VRChat 同期予算解析を束ねて返す。REQ-PM-12。

    返り値: {schema: {...}, budget: {...}|None, suggestions: list[str]}
    スキーマが無効な場合は budget/suggestions を算出しない。
    """
    schema = validate_preset_schema(preset)
    result: Dict[str, Any] = {"schema": schema, "budget": None, "suggestions": []}
    if schema["valid"]:
        params = preset["parameters"]
        result["budget"] = vpb.analyze_budget(params)
        result["suggestions"] = vpb.suggest_optimizations(params)
    return result
