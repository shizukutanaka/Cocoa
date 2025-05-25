import json
import os
from typing import Dict, Any

def add_custom_parameter(preset_path: str, param_name: str, param_value: Any, out_path: str = None):
    """
    Add or update a custom parameter in a preset JSON file.
    If out_path is not specified, overwrite the original file.
    """
    with open(preset_path, 'r', encoding='utf-8') as f:
        preset = json.load(f)
    preset[param_name] = param_value
    if out_path is None:
        out_path = preset_path
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(preset, f, ensure_ascii=False, indent=2)
    print(f"Parameter '{param_name}' set to '{param_value}' in {out_path}")

def batch_add_parameter(preset_dir: str, param_name: str, param_value: Any):
    """
    Add or update a custom parameter in all preset JSON files in a directory.
    """
    for fname in os.listdir(preset_dir):
        if fname.endswith('.json'):
            path = os.path.join(preset_dir, fname)
            add_custom_parameter(path, param_name, param_value)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Satin Preset Parameter Extension Tool")
    parser.add_argument("preset", help="Preset file or directory")
    parser.add_argument("param_name", help="Parameter name to add/update")
    parser.add_argument("param_value", help="Parameter value (interpreted as string)")
    parser.add_argument("--batch", action="store_true", help="Apply to all presets in directory")
    args = parser.parse_args()
    if args.batch:
        batch_add_parameter(args.preset, args.param_name, args.param_value)
    else:
        add_custom_parameter(args.preset, args.param_name, args.param_value)
