# main/vrchat_parameter_budget.py
"""
VRChat Avatar 3.0 同期パラメータの予算モデル（仕様: docs/SPEC_PRESET_PARAMETERS.md）

VRChat はアバターのユーザ定義 Expression Parameter を最大 256 ビットまでネットワーク
同期できる。各パラメータのコストは型で決まる:

    Bool / Trigger = 1 bit,  Int / Float = 8 bits

`synced=False`（ローカル専用）のパラメータは予算に計上されない。

本モジュールは依存ライブラリ無し（標準ライブラリのみ）で、コスト計算・予算判定・
最適化提案を提供する。REQ-PM-09 / REQ-PM-10 / REQ-PM-11。
"""
from __future__ import annotations

from typing import Any, Dict, List

# 同期パラメータ予算（ビット）。VRChat のユーザ定義パラメータ上限。
SYNC_PARAMETER_BUDGET_BITS = 256

# 型 -> 同期コスト(ビット)
_TYPE_COST_BITS: Dict[str, int] = {
    "bool": 1,
    "trigger": 1,
    "int": 8,
    "float": 8,
}


def _normalize_type(param_type: Any) -> str:
    if not isinstance(param_type, str):
        raise ValueError(f"parameter 'type' must be a string, got {type(param_type).__name__}")
    key = param_type.strip().lower()
    if key not in _TYPE_COST_BITS:
        raise ValueError(
            f"unknown parameter type '{param_type}'. "
            f"Expected one of: Bool, Int, Float, Trigger"
        )
    return key


def parameter_cost(param: Dict[str, Any]) -> int:
    """1 パラメータの同期コスト(ビット)を返す。REQ-PM-09。

    `synced` が明示的に False のものは 0（既定は同期=True）。
    """
    if not param.get("synced", True):
        return 0
    return _TYPE_COST_BITS[_normalize_type(param.get("type"))]


def calculate_sync_cost(parameters: List[Dict[str, Any]]) -> int:
    """同期パラメータ群の合計コスト(ビット)。"""
    return sum(parameter_cost(p) for p in parameters)


def analyze_budget(parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """予算使用状況を解析して返す。REQ-PM-10。"""
    breakdown: Dict[str, int] = {"Bool": 0, "Trigger": 0, "Int": 0, "Float": 0}
    per_type_bits: Dict[str, int] = {"Bool": 0, "Trigger": 0, "Int": 0, "Float": 0}
    synced_count = 0

    for p in parameters:
        if not p.get("synced", True):
            continue
        key = _normalize_type(p.get("type"))
        label = key.capitalize()
        breakdown[label] += 1
        per_type_bits[label] += _TYPE_COST_BITS[key]
        synced_count += 1

    used = sum(per_type_bits.values())
    return {
        "budget_bits": SYNC_PARAMETER_BUDGET_BITS,
        "used_bits": used,
        "remaining_bits": SYNC_PARAMETER_BUDGET_BITS - used,
        "over_budget": used > SYNC_PARAMETER_BUDGET_BITS,
        "synced_count": synced_count,
        "breakdown": breakdown,
        "per_type_bits": per_type_bits,
    }


def _looks_binary(default: Any) -> bool:
    """default 値が 0/1（または False/True）の二値とみなせるか。"""
    if isinstance(default, bool):
        return True
    if isinstance(default, (int, float)):
        return default in (0, 1)
    return False


def suggest_optimizations(parameters: List[Dict[str, Any]]) -> List[str]:
    """予算超過時の削減提案を返す。予算内なら空リスト。REQ-PM-11。"""
    analysis = analyze_budget(parameters)
    if not analysis["over_budget"]:
        return []

    suggestions: List[str] = []

    # 1) 二値とみなせる Float は Bool 化（8 -> 1 bit, 7bit 削減）
    binary_floats = [
        p.get("name", "?")
        for p in parameters
        if p.get("synced", True)
        and _normalize_type_safe(p.get("type")) == "float"
        and _looks_binary(p.get("default"))
    ]
    suggestions.extend(
        f"パラメータ '{name}' は二値です。Float→Bool に変更すると 7 ビット削減できます。"
        for name in binary_floats
    )

    # 2) ローカル用途と思われる命名は未同期化
    local_like = [
        p.get("name", "?")
        for p in parameters
        if p.get("synced", True) and "local" in str(p.get("name", "")).lower()
    ]
    suggestions.extend(
        f"パラメータ '{name}' はローカル用途の可能性があります。synced=False で予算から外せます。"
        for name in local_like
    )

    # 3) なお超過する場合の総括
    over_by = analysis["used_bits"] - SYNC_PARAMETER_BUDGET_BITS
    suggestions.append(
        f"同期予算を {over_by} ビット超過しています（{analysis['used_bits']}/{SYNC_PARAMETER_BUDGET_BITS}）。"
        "残りは OSC ビットパッキングで複数 Float を集約することを検討してください。"
    )
    return suggestions


def _normalize_type_safe(param_type: Any) -> str:
    """提案生成用: 未知型でも例外を出さず空文字を返す。"""
    try:
        return _normalize_type(param_type)
    except ValueError:
        return ""
