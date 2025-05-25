import os
import json
import csv
import glob
import argparse

def export_presets_to_csv(target_dir, out_csv):
    files = glob.glob(os.path.join(target_dir, "*.json"))
    rows = []
    fieldnames = set()
    # 1度全ファイル走査して全キーを抽出
    for fpath in files:
        with open(fpath, encoding="utf-8") as f:
            try:
                data = json.load(f)
                data["__filename__"] = os.path.basename(fpath)
                rows.append(data)
                fieldnames.update(data.keys())
            except Exception:
                continue
    fieldnames = sorted(fieldnames)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"{len(rows)}件をCSV出力: {out_csv}")

def import_presets_from_csv(csv_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            fname = row.get("__filename__")
            if not fname:
                fname = f"preset_{count:03d}.json"
            path = os.path.join(out_dir, fname)
            # __filename__はJSONには含めない
            data = {k: v for k, v in row.items() if k != "__filename__"}
            # listやbool等の型補正（簡易）
            for k, v in data.items():
                if v == "True":
                    data[k] = True
                elif v == "False":
                    data[k] = False
                elif v.startswith("[") and v.endswith("]"):
                    try:
                        data[k] = json.loads(v)
                    except Exception:
                        pass
            with open(path, "w", encoding="utf-8") as wf:
                json.dump(data, wf, ensure_ascii=False, indent=2)
            count += 1
    print(f"{count}件をCSVからJSONにインポート: {out_dir}")

def main():
    parser = argparse.ArgumentParser(description="プリセットCSVエクスポート/インポートツール")
    subparsers = parser.add_subparsers(dest='command')

    exp = subparsers.add_parser('export', help='プリセットをCSV出力')
    exp.add_argument('dir', help='プリセットjson格納ディレクトリ')
    exp.add_argument('--csv', default='presets.csv', help='出力CSVファイル名')

    imp = subparsers.add_parser('import', help='CSVからプリセットJSON生成')
    imp.add_argument('csv', help='入力CSVファイル')
    imp.add_argument('--outdir', default='imported_presets', help='出力ディレクトリ')

    args = parser.parse_args()
    if args.command == 'export':
        export_presets_to_csv(args.dir, args.csv)
    elif args.command == 'import':
        import_presets_from_csv(args.csv, args.outdir)
    else:
        print('export/importサブコマンドを指定してください')

if __name__ == "__main__":
    main()
