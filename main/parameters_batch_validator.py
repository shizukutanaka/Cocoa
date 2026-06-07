import json
import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)

_TYPE_WHITELIST: Dict[str, type] = {
    "bool": bool,
    "int": int,
    "float": float,
    "str": str,
    "list": list,
    "dict": dict,
}


def _parse_type_map(type_map: dict) -> Dict[str, type]:
    """Convert a {field: type_name_str} dict to {field: type} using an allowlist.

    Raises ValueError for unrecognised type names (prevents eval-based injection).
    """
    result: Dict[str, type] = {}
    for k, v in type_map.items():
        if v not in _TYPE_WHITELIST:
            raise ValueError(f"Unsupported type: {v!r}. Allowed: {sorted(_TYPE_WHITELIST)}")
        result[k] = _TYPE_WHITELIST[v]
    return result


def validate_parameter_types(preset: dict, param_types: Dict[str, type]) -> Dict[str, str]:
    """Return a dict of field→error for any type mismatches in *preset*.

    Keys present in *param_types* but absent from *preset* are skipped silently.
    """
    errors: Dict[str, str] = {}
    for k, expected_type in param_types.items():
        if k in preset:
            v = preset[k]
            if not isinstance(v, expected_type):
                errors[k] = f"Expected {expected_type.__name__}, got {type(v).__name__}"
    return errors


def batch_validate_presets(preset_dir: str, param_types: Dict[str, type]) -> dict:
    """Validate all *.json* files in *preset_dir* against *param_types*.

    Returns::

        {
          "errors":  {filename: {field: msg, ...}, ...},   # only files with errors
          "summary": {"total": N, "passed": N, "failed": N}
        }

    If *preset_dir* does not exist or is not a directory the summary gets an
    extra ``"error"`` key and no files are processed (no exception is raised).
    """
    base = {"errors": {}, "summary": {"total": 0, "passed": 0, "failed": 0}}

    if not os.path.isdir(preset_dir):
        base["summary"]["error"] = f"Directory not found or not a directory: {preset_dir}"
        return base

    errors: Dict[str, Dict[str, str]] = {}
    total = passed = failed = 0

    for fname in os.listdir(preset_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(preset_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                preset = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping %s: %s", fname, exc)
            continue

        total += 1
        field_errors = validate_parameter_types(preset, param_types)
        if field_errors:
            errors[fname] = field_errors
            failed += 1
        else:
            passed += 1

    base["errors"] = errors
    base["summary"] = {"total": total, "passed": passed, "failed": failed}
    return base


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Satin Batch Parameter Type Validator")
    parser.add_argument("preset_dir", help="Preset directory")
    parser.add_argument("param_types_json", help="JSON file: {field: type_name} (bool/int/float/str/list/dict)")
    parser.add_argument("--report", default="type_validation_report.json", help="Output report file")
    args = parser.parse_args()

    with open(args.param_types_json, "r", encoding="utf-8") as f:
        raw_map = json.load(f)

    try:
        param_types = _parse_type_map(raw_map)
    except ValueError as exc:
        print(f"Error in type map: {exc}")
        raise SystemExit(1)

    result = batch_validate_presets(args.preset_dir, param_types)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    s = result["summary"]
    print(f"Validation report saved: {args.report}  (total={s['total']}, passed={s['passed']}, failed={s['failed']})")


if __name__ == "__main__":
    main()
