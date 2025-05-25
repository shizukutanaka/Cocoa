import json
import sys

def load_preset(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def diff_presets(preset1, preset2):
    diff = {}
    keys = set(preset1.keys()) | set(preset2.keys())
    for key in keys:
        v1 = preset1.get(key)
        v2 = preset2.get(key)
        if v1 != v2:
            diff[key] = {"A": v1, "B": v2}
    return diff

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python avatar_preset_diff.py <presetA.json> <presetB.json>")
        sys.exit(1)
    p1 = load_preset(sys.argv[1])
    p2 = load_preset(sys.argv[2])
    diff = diff_presets(p1, p2)
    if not diff:
        print("No differences found.")
    else:
        print("Differences:")
        for k, v in diff.items():
            print(f"{k}: {v['A']} -> {v['B']}")
