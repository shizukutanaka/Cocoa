import os
import json
import shutil
import glob
from datetime import datetime
from parameters_batch_validator import validate_parameters

def backup_file(filepath, backup_dir):
    os.makedirs(backup_dir, exist_ok=True)
    base = os.path.basename(filepath)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f"{base}.{ts}.bak")
    shutil.copy2(filepath, backup_path)
    return backup_path

def repair_preset(data):
    # シンプルな自動修復例: 必須キー追加・型修正
    required_keys = {"name": "unknown", "parameters": []}
    for k, v in required_keys.items():
        if k not in data:
            data[k] = v
    if not isinstance(data.get("parameters", []), list):
        data["parameters"] = []
    return data

def validate_and_repair_dir(target_dir, backup_dir="preset_backups", report_path=None):
    preset_files = glob.glob(os.path.join(target_dir, "*.json"))
    report = []
    for pf in preset_files:
        with open(pf, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception as e:
                report.append({"file": pf, "error": f"JSON decode error: {e}"})
                continue
        errors = validate_parameters(data)
        if errors:
            backup_file(pf, backup_dir)
            fixed = repair_preset(data)
            with open(pf, "w", encoding="utf-8") as f:
                json.dump(fixed, f, ensure_ascii=False, indent=2)
            report.append({"file": pf, "status": "repaired", "errors": errors})
        else:
            report.append({"file": pf, "status": "ok"})
    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    return report

def main():
    import argparse
    parser = argparse.ArgumentParser(description="プリセット一括バリデーション＆自動修復ツール")
    parser.add_argument("dir", help="プリセットjson格納ディレクトリ")
    parser.add_argument("--backup", default="preset_backups", help="バックアップ保存先")
    parser.add_argument("--report", default=None, help="レポートjson出力パス")
    args = parser.parse_args()
    rep = validate_and_repair_dir(args.dir, args.backup, args.report)
    print(f"{len(rep)}件を検査・修復しました。詳細はレポートまたは標準出力を参照")
    for r in rep:
        print(r)

if __name__ == "__main__":
    main()
