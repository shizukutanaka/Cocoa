import json
import os
import shutil
from datetime import datetime
from typing import Dict

class PresetVersionManager:
    def __init__(self, preset_dir: str, version_dir: str):
        self.preset_dir = preset_dir
        self.version_dir = version_dir
        os.makedirs(self.version_dir, exist_ok=True)

    def save_version(self, preset_name: str, retry=2):
        src = os.path.join(self.preset_dir, preset_name)
        if not os.path.isfile(src):
            print(f"[ERROR] {preset_name} does not exist in {self.preset_dir}")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ver_name = f"{preset_name.replace('.json', '')}_v{timestamp}.json"
        dst = os.path.join(self.version_dir, ver_name)
        # 重複保存防止
        if os.path.exists(dst):
            print(f"[WARN] Version already exists: {dst}")
            return
        for i in range(retry):
            try:
                shutil.copy2(src, dst)
                print(f"Version saved: {dst}")
                return
            except Exception as e:
                print(f"[WARN] Failed to save version: {e}, retry {i+1}/{retry}")
        print(f"[ERROR] Could not save version after {retry} attempts.")

    def list_versions(self, preset_base: str, detail: bool = False):
        prefix = preset_base.replace('.json', '')
        files = [f for f in os.listdir(self.version_dir) if f.startswith(prefix)]
        files.sort()
        if detail:
            for f in files:
                path = os.path.join(self.version_dir, f)
                stat = os.stat(path)
                dt = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                size = stat.st_size
                print(f"{f}\t{dt}\t{size} bytes")
        return files

    def restore_version(self, preset_base: str, version_file: str, retry=2):
        src = os.path.join(self.version_dir, version_file)
        dst = os.path.join(self.preset_dir, preset_base)
        if not os.path.isfile(src):
            print(f"[ERROR] Version file not found: {src}")
            return
        for i in range(retry):
            try:
                shutil.copy2(src, dst)
                print(f"Restored {preset_base} from {version_file}")
                return
            except Exception as e:
                print(f"[WARN] Failed to restore: {e}, retry {i+1}/{retry}")
        print(f"[ERROR] Could not restore version after {retry} attempts.")

    def delete_version(self, version_file: str):
        path = os.path.join(self.version_dir, version_file)
        try:
            os.remove(path)
            print(f"Deleted version: {version_file}")
        except Exception as e:
            print(f"[ERROR] Failed to delete {version_file}: {e}")

    def diff_versions(self, version_file1: str, version_file2: str):
        try:
            with open(os.path.join(self.version_dir, version_file1), encoding='utf-8') as f1:
                v1 = json.load(f1)
            with open(os.path.join(self.version_dir, version_file2), encoding='utf-8') as f2:
                v2 = json.load(f2)
        except Exception as e:
            print(f"[ERROR] Failed to load versions for diff: {e}")
            return
        # 差分表示（簡易）
        keys = set(v1.keys()) | set(v2.keys())
        diff = {}
        for k in keys:
            if v1.get(k) != v2.get(k):
                diff[k] = {'A': v1.get(k), 'B': v2.get(k)}
        if diff:
            print(json.dumps(diff, ensure_ascii=False, indent=2))
        else:
            print("No difference between versions.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Satin Preset Version Manager")
    parser.add_argument("preset_dir", help="Preset directory")
    parser.add_argument("version_dir", help="Version history directory")
    subparsers = parser.add_subparsers(dest="command")

    save_parser = subparsers.add_parser("save", help="Save new version")
    save_parser.add_argument("preset_name")

    list_parser = subparsers.add_parser("list", help="List versions")
    list_parser.add_argument("preset_base")
    list_parser.add_argument("--detail", action="store_true", help="Show details")

    diff_parser = subparsers.add_parser("diff", help="Diff two versions")
    diff_parser.add_argument("version_file1")
    diff_parser.add_argument("version_file2")

    delete_parser = subparsers.add_parser("delete", help="Delete version file")
    delete_parser.add_argument("version_file")

    restore_parser = subparsers.add_parser("restore", help="Restore version")
    restore_parser.add_argument("preset_base")
    restore_parser.add_argument("version_file")

    args = parser.parse_args()
    mgr = PresetVersionManager(args.preset_dir, args.version_dir)

    if args.command == "save":
        mgr.save_version(args.preset_name)
    elif args.command == "list":
        versions = mgr.list_versions(args.preset_base, detail=getattr(args, 'detail', False))
        if not getattr(args, 'detail', False):
            print("\n".join(versions) if versions else "No versions found.")
    elif args.command == "diff":
        mgr.diff_versions(args.version_file1, args.version_file2)
    elif args.command == "delete":
        mgr.delete_version(args.version_file)
    elif args.command == "restore":
        mgr.restore_version(args.preset_base, args.version_file)
    else:
        parser.print_help()
