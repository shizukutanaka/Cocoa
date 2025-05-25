import json
import os
from typing import Any, Dict

def validate_parameter_types(preset: dict, param_types: Dict[str, type]) -> Dict[str, str]:
    errors = {}
    for k, expected_type in param_types.items():
        if k in preset:
            v = preset[k]
            if not isinstance(v, expected_type):
                errors[k] = f"Expected {expected_type.__name__}, got {type(v).__name__}"
    return errors

def batch_validate_presets(preset_dir: str, param_types: Dict[str, type]):
    results = {}
    for fname in os.listdir(preset_dir):
        if fname.endswith('.json'):
            path = os.path.join(preset_dir, fname)
            with open(path, 'r', encoding='utf-8') as f:
                preset = json.load(f)
            errors = validate_parameter_types(preset, param_types)
            if errors:
                results[fname] = errors
    return results

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Satin Batch Parameter Type Validator")
    parser.add_argument("preset_dir", help="Preset directory")
    parser.add_argument("param_types_json", help="JSON file specifying parameter types (e.g. {\"height\": \"int\", ...})")
    parser.add_argument("--report", default="type_validation_report.json", help="Output report file")
    args = parser.parse_args()

    with open(args.param_types_json, 'r', encoding='utf-8') as f:
        type_map = json.load(f)
    # Map string type names to Python types
    type_dict = {k: eval(v) for k, v in type_map.items()}
    results = batch_validate_presets(args.preset_dir, type_dict)
    with open(args.report, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Validation report saved: {args.report}")

if __name__ == "__main__":
    main()
