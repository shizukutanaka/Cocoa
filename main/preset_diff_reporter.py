import json
import os
from typing import List, Dict

import time
import logging
import argparse

def load_preset(path, retry=2):
    for i in range(retry):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"[WARN] Failed to load {path}: {e}")
            time.sleep(0.2)
    logging.error(f"[ERROR] Failed to load {path} after {retry} retries.")
    return {}

def diff_presets(preset1: dict, preset2: dict) -> Dict[str, dict]:
    diff = {}
    keys = set(preset1.keys()) | set(preset2.keys())
    for key in keys:
        v1 = preset1.get(key)
        v2 = preset2.get(key)
        if v1 != v2:
            diff[key] = {"A": v1, "B": v2}
    return diff

def diff_all_presets(dirA: str, dirB: str, report_path: str, summary: bool = True):
    filesA = {f for f in os.listdir(dirA) if f.endswith('.json')}
    filesB = {f for f in os.listdir(dirB) if f.endswith('.json')}
    common = filesA & filesB
    report = {}
    t0 = time.time()
    total = len(common)
    changed = 0
    for idx, fname in enumerate(sorted(common), 1):
        try:
            p1 = load_preset(os.path.join(dirA, fname))
            p2 = load_preset(os.path.join(dirB, fname))
            diff = diff_presets(p1, p2)
            if diff:
                report[fname] = diff
                changed += 1
        except Exception as e:
            logging.error(f"[ERROR] Diff failed for {fname}: {e}")
        if idx % 10 == 0 or idx == total:
            print(f"[{idx}/{total}] processed...")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    t1 = time.time()
    print(f"Diff report generated: {report_path}")
    print(f"Compared: {total} files, Changed: {changed}, Time: {t1-t0:.2f}s")
    if summary:
        print(f"Summary: {changed}/{total} presets differ.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Satin Bulk Preset Diff Reporter")
    parser.add_argument("dirA", help="First preset directory")
    parser.add_argument("dirB", help="Second preset directory")
    parser.add_argument("report", help="Output report JSON file")
    parser.add_argument("--log", help="Log file for errors/progress")
    parser.add_argument("--no-summary", action="store_true", help="Do not print summary")
    args = parser.parse_args()
    if args.log:
        logging.basicConfig(filename=args.log, level=logging.INFO)
    else:
        logging.basicConfig(level=logging.INFO)
    diff_all_presets(args.dirA, args.dirB, args.report, summary=(not args.no_summary))
