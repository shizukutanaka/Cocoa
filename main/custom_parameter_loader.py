import json
import os
from utils_profile import profile_time, log_info, log_error
from utils_batch import batch_process

def load_custom_parameters(param_dir="."):
    params = []
    for fname in os.listdir(param_dir):
        if fname.startswith("custom_parameter") and fname.endswith(".json"):
            path = os.path.join(param_dir, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    param = json.load(f)
                    params.append(param)
            except Exception as e:
                print(f"[WARN] {fname} 読み込み失敗: {e}"); log_error(f"{fname} 読み込み失敗: {e}")
    return params

def validate_parameter(param, value):
    t = param.get("type")
    if t == "string":
        return isinstance(value, str)
    elif t == "int":
        return isinstance(value, int)
    elif t == "float":
        return isinstance(value, float)
    elif t == "bool":
        return isinstance(value, bool)
    elif t == "select":
        return value in param.get("options", [])
    return False

def print_parameters(params):
    for p in params:
        print(f"- {p.get('name')} ({p.get('type')}) [default: {p.get('default')}] : {p.get('description')}")
        if p.get("options"):
            print(f"  options: {p['options']}")

def create_parameter_template():
    template = {
        "name": "param_name",
        "type": "string",
        "default": "",
        "description": "ここに説明を記入",
        "options": []
    }
    # 入力とバリデーション
    fname = input("新しいパラメータ名（例: height）: ").strip()
    while not fname:
        fname = input("パラメータ名は必須です。再入力: ").strip()
    # 型選択
    allowed_types = ["string", "int", "float", "bool", "select"]
    while True:
        ptype = input(f"型 {allowed_types} から選択: ").strip()
        if ptype in allowed_types:
            break
        print("[WARN] 型は string/int/float/bool/select のいずれかです。")
    desc = input("説明: ").strip()
    # デフォルト値バリデーション
    while True:
        default = input("デフォルト値: ").strip()
        try:
            if ptype == "int":
                default_val = int(default)
            elif ptype == "float":
                default_val = float(default)
            elif ptype == "bool":
                if default.lower() in ["true", "1", "yes", "on"]:
                    default_val = True
                elif default.lower() in ["false", "0", "no", "off"]:
                    default_val = False
                else:
                    raise ValueError()
            else:
                default_val = default
            break
        except Exception:
            print("[WARN] デフォルト値が型と一致しません。再入力してください。")
    opts = []
    if ptype == "select":
        while True:
            opts = input("選択肢（カンマ区切り、2つ以上）: ").split(",")
            opts = [o.strip() for o in opts if o.strip()]
            if len(opts) >= 2:
                break
            print("[WARN] select型は2つ以上の選択肢が必要です。")
    template["name"] = fname
    template["type"] = ptype
    template["description"] = desc
    template["default"] = default_val
    if opts:
        template["options"] = opts
    # サマリ表示＆確認
    print("\n[SUMMARY] 作成されるパラメータ:")
    print(json.dumps(template, ensure_ascii=False, indent=2))
    confirm = input("この内容で保存しますか？ [y/N]: ").strip().lower()
    if confirm != "y":
        print("[INFO] キャンセルされました")
        return
    outname = f"custom_parameter_{fname}.json"
    try:
        with open(outname, "w", encoding="utf-8") as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] テンプレート保存失敗: {e}"); log_error(f"{outname} テンプレート保存失敗: {e}")
        return
    print(f"[INFO] テンプレートを {outname} に保存しました")

if __name__ == "__main__":
    params = load_custom_parameters()
    print("[INFO] 検出されたカスタムパラメータ:")
    print_parameters(params)
    # サンプル: バリデーション
    for p in params:
        v = p.get("default")
        ok = validate_parameter(p, v)
        print(f"  → default値バリデーション: {'OK' if ok else 'NG'}")
    # 追加: 新規パラメータ作成インタラクティブCLI
    ans = input("新しいカスタムパラメータを作成しますか？ [y/N]: ")
    while ans.lower() == "y":
        create_parameter_template()
        ans = input("続けて別のカスタムパラメータも作成しますか？ [y/N]: ")

    # 追加: 既存テンプレートの一覧・削除機能
    def list_and_delete_templates():
        import glob
        files = sorted(glob.glob("custom_parameter_*.json"))
        if not files:
            print("[INFO] 削除可能なカスタムパラメータテンプレートはありません。")
            return
        print("\n[INFO] 現在のカスタムパラメータテンプレート:")
        for i, f in enumerate(files):
            print(f"  [{i+1}] {f}")
        sel = input("削除したいテンプレート番号またはファイル名を入力（キャンセルは空Enter）: ").strip()
        if not sel:
            print("[INFO] 削除操作をキャンセルしました。")
            return
        try:
        else:
            log_error(f"{fname} が存在しません")
            return f"[WARN] {fname} が存在しません"
    results = batch_process(delete_one, names, desc="削除中")
    for msg in results:
        print(msg)
        else:
            log_info("[INFO] 削除操作をキャンセルしました。")

    ans2 = input("既存のカスタムパラメータテンプレートを一覧・削除しますか？ [y/N]: ")
    if ans2.lower() == "y":
{{ ... }}
            except Exception as e:
                log_info(f"[WARN] {fname} の読み込みに失敗: {e}")
        if not all_params:
            log_info("[WARN] 有効なテンプレートがありません。")
            return
        outfname = "custom_parameters_export.json"
@profile_time
def export_templates():
    params = load_custom_parameters()
    # 並列でダミー変換（例：将来の拡張用）
    def export_one(p):
        return p
    results = batch_process(export_one, params, desc="エクスポート中")
    with open("custom_parameters_export.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log_info("テンプレートを custom_parameters_export.json にエクスポートしました")
        except Exception as e:
            log_error(f"[ERROR] エクスポート失敗: {e}")

    ans6 = input("全カスタムパラメータテンプレートを一括エクスポートしますか？ [y/N]: ")
    if ans6.lower() == "y":
{{ ... }}
    ans11 = input("テンプレートの name/type 重複をチェックしますか？ [y/N]: ")
    if ans11.lower() == "y":
        check_duplicates()

    # 追加: テンプレートのバリデーションチェック機能
    @profile_time
def validate_templates():
    params = load_custom_parameters()
    errors = []
    def validate_one(p):
        # ...
        # 省略
        return None  # エラーなければNone, あればエラー内容
    # 並列バッチ検証
    results = batch_process(validate_one, params, desc="バリデーション中")
    errors = [r for r in results if r]
    if errors:
        for e in errors:
            print(e)
        log_error("テンプレートバリデーションエラーあり")
    else:
        log_info("全テンプレートが正常です")
name","type","default","description"]
        allowed_types = ["string","int","float","bool","select"]
        issues = []
        for fname in files:
            try:
                with open(fname, encoding="utf-8") as f:
{{ ... }}
        if not files:
            log_info("[INFO] レポート出力対象のテンプレートがありません。")
            return
        params = []
        for fname in files:
           @profile_time
def import_templates():
    try:
        with open("custom_parameters_export.json", encoding="utf-8") as f:
            params = json.load(f)
    except Exception as e:
        log_error(f"[ERROR] インポート失敗: {e}")
        return
    def import_one(p):
        fname = f"custom_parameter_{p['name']}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
        return fname
    batch_process(import_one, params, desc="インポート中")
    log_info("インポート完了")
総数: {len(params)}\n\n")
            f.write("| name | type | default | description | options |\n")
            f.write("|------|------|---------|-------------|---------|\n")
            for p in params:
                opts = ', '.join(p.get('options', [])) if isinstance(p.get('options', []), list) else ''
                f.write(f"| {p.get('name','')} | {p.get('type','')} | {str(p.get('default',''))} | {p.get('description','')} | {opts} |\n")
{{ ... }}
            f.write("\n---\n\n")
            f.write("## 詳細一覧\n\n")
            for p in params:
                f.write(f"### {p.get('name','')}\n")
                f.write(f"- type: {p.get('type','')}\n")
                f.write(f"- default: {str(p.get('default',''))}\n")
                f.write(f"- description: {p.get('description','')}\n")
                if p.get('type') == 'select':
                    f.write(f"- options: {', '.join(p.get('options', []))}\n")
                f.write("\n")
        print(f"[INFO] Markdownレポートを {outfname} に出力しました。")

    ans18 = input("テンプレート一覧をMarkdownレポートとして出力しますか？ [y/N]: ")
    if ans18.lower() == "y":
        export_markdown_report()

    # 追加: テンプレート一覧のCSVエクスポート機能
    @profile_time
    def export_csv():
        import glob, csv
        files = sorted(glob.glob("custom_parameter_*.json"))
        if not files:
            log_info("[INFO] CSV出力対象のテンプレートがありません。")
            return
        params = []
        for fname in files:
            try:
                with open(fname, encoding="utf-8") as f:
                    data = json.load(f)
                params.append(data)
            except Exception as e:
                log_error(f"[WARN] {fname} 読み込み失敗: {e}")
                continue
        outfname = "custom_parameters_export.csv"
        def to_csv_row(p):
            opts = ', '.join(p.get('options', [])) if isinstance(p.get('options', []), list) else ''
            return [
                p.get('name',''),
                p.get('type',''),
                str(p.get('default','')),
                p.get('description',''),
                opts
            ]
        try:
            rows = batch_process(to_csv_row, params, desc="CSV変換中")
            with open(outfname, "w", encoding="utf-8", newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["name","type","default","description","options"])
                for row in rows:
                    writer.writerow(row)
            log_info(f"CSVエクスポートを {outfname} に出力しました。")
        except Exception as e:
            log_error(f"[ERROR] CSVエクスポート失敗: {e}")

    ans19 = input("テンプレート一覧をCSVファイルとしてエクスポートしますか？ [y/N]: ")
    if ans19.lower() == "y":
        export_csv()

    # 追加: CSVからテンプレート一括インポート・更新機能
    @profile_time
    def import_csv():
        import csv, os, json
        infname = "custom_parameters_import.csv"
        if not os.path.exists(infname):
            log_info(f"[INFO] {infname} が存在しません。エクスポートしたCSVを編集して保存してください。")
            return
        imported, updated, failed = 0, 0, 0
        rows = []
        with open(infname, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        def import_one(row):
            name = row.get("name","").strip()
            if not name:
                log_error("[WARN] 名前未設定の行をスキップ")
                return "skipped"
            fname = f"custom_parameter_{name}.json"
            param = {
                "name": name,
                "type": row.get("type","string"),
                "default": row.get("default",""),
                "description": row.get("description",""),
            }
            opts = row.get("options","")
            if opts:
                param["options"] = [o.strip() for o in opts.split(",") if o.strip()]
            try:
                with open(fname, "w", encoding="utf-8") as f:
                    json.dump(param, f, ensure_ascii=False, indent=2)
                log_info(f"[INFO] {fname} をインポート・更新")
                return "imported"
            except Exception as e:
                log_error(f"[ERROR] {fname} インポート失敗: {e}")
                return "failed"
        results = batch_process(import_one, rows, desc="CSVインポート中")
        imported = results.count("imported")
        failed = results.count("failed")
        skipped = results.count("skipped")
        log_info(f"[SUMMARY] CSVインポート完了: {imported}件, スキップ: {skipped}件, エラー: {failed}件")
                if param["type"] == "select":
                    param["options"] = [o.strip() for o in opts.split(",") if o.strip()]
                    if param["default"] not in param["options"] and param["options"]:
                        param["default"] = param["options"][0]
                # 型変換
                if param["type"] == "int":
                    try: param["default"] = int(param["default"])
                    except: param["default"] = 0
                elif param["type"] == "float":
                    try: param["default"] = float(param["default"])
                    except: param["default"] = 0.0
                elif param["type"] == "bool":
                    param["default"] = str(param["default"]).lower() in ["true","1","yes"]
                # 保存
                existed = os.path.exists(fname)
                try:
                    with open(fname, "w", encoding="utf-8") as wf:
                        json.dump(param, wf, ensure_ascii=False, indent=2)
                    if existed:
                        updated += 1
                    else:
                        imported += 1
                except Exception as e:
                    print(f"[ERROR] {fname} 書き込み失敗: {e}"); log_error(f"{fname} 書き込み失敗: {e}"); failed += 1
        print(f"[SUMMARY] CSVインポート: 新規 {imported}件, 更新 {updated}件, 失敗 {failed}件")

    ans20 = input("custom_parameters_import.csv からテンプレートを一括インポート・更新しますか？ [y/N]: ")
    if ans20.lower() == "y":
        import_csv()

    # 追加: 未使用テンプレート（オーファン）検出機能
    def detect_orphan_templates():
        import glob, os, json
        files = sorted(glob.glob("custom_parameter_*.json"))
        if not files:
            print("[INFO] 検出対象のテンプレートがありません。")
            return
        config_files = [f for f in os.listdir('.') if f.endswith('avatar_config.json')]
        referenced = set()
        for cfg in config_files:
            try:
                with open(cfg, encoding="utf-8") as f:
                    cfgdata = json.load(f)
                # 仮定: config内で "custom_parameters": ["param1", "param2", ...] 形式
                param_names = cfgdata.get("custom_parameters", [])
                referenced.update(param_names)
            except Exception as e:
                print(f"[WARN] {cfg} の解析失敗: {e}"); log_error(f"{cfg} の解析失敗: {e}")
        orphan = []
        for fname in files:
            try:
                with open(fname, encoding="utf-8") as f:
                    data = json.load(f)
                name = data.get("name", fname)
                if name not in referenced:
                    orphan.append(fname)
            except Exception as e:
                continue
        print(f"[SUMMARY] 未使用テンプレート: {len(orphan)}件")
        for o in orphan:
            print(f"  [ORPHAN] {o}")
        if not orphan:
            print("[INFO] すべてのテンプレートが参照されています。")

    ans21 = input("未使用（オーファン）テンプレートを検出しますか？ [y/N]: ")
    if ans21.lower() == "y":
        detect_orphan_templates()

    # 追加: 未使用テンプレート一括削除機能
    def delete_orphan_templates():
        import glob, os, json
        files = sorted(glob.glob("custom_parameter_*.json"))
        if not files:
            print("[INFO] 削除対象のテンプレートがありません。")
            return
        config_files = [f for f in os.listdir('.') if f.endswith('avatar_config.json')]
        referenced = set()
        for cfg in config_files:
            try:
                with open(cfg, encoding="utf-8") as f:
                    cfgdata = json.load(f)
                param_names = cfgdata.get("custom_parameters", [])
                referenced.update(param_names)
            except Exception as e:
                continue
        orphan = []
        for fname in files:
            try:
                with open(fname, encoding="utf-8") as f:
                    data = json.load(f)
                name = data.get("name", fname)
                if name not in referenced:
                    orphan.append(fname)
            except Exception as e:
                continue
        if not orphan:
            print("[INFO] 削除対象の未使用テンプレートはありません。")
            return
        print(f"[INFO] 削除対象の未使用テンプレート: {len(orphan)}件")
        for o in orphan:
            print(f"  [ORPHAN] {o}")
        confirm = input("これらの未使用テンプレートを一括削除しますか？ [y/N]: ").strip().lower()
        if confirm != 'y':
            print("[INFO] 削除をキャンセルしました。"); return
        deleted, failed = 0, 0
        for o in orphan:
            try:
                os.remove(o)
                print(f"[DELETED] {o}")
                deleted += 1
            except Exception as e:
                print(f"[ERROR] {o} の削除失敗: {e}"); log_error(f"{o} の削除失敗: {e}"); failed += 1
        print(f"[SUMMARY] 未使用テンプレート削除: {deleted}件, 失敗: {failed}件")

    ans22 = input("未使用テンプレートを一括削除しますか？ [y/N]: ")
    if ans22.lower() == "y":
        delete_orphan_templates()

    # 追加: エラー自動ログ収集・レポート化機能
    ERROR_LOG = "custom_parameter_error.log"
    def log_error(msg):
        from datetime import datetime
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

    def show_error_log():
        if not os.path.exists(ERROR_LOG):
            print("[INFO] エラーログはまだありません。")
            return
        with open(ERROR_LOG, encoding="utf-8") as f:
            lines = f.readlines()
        print(f"[INFO] エラーログ（最新{len(lines)}件）:")
        for line in lines[-50:]:
            print(line.rstrip())
        exp = input("Markdownレポートとして出力しますか？ [y/N]: ").strip().lower()
        if exp == 'y':
            outmd = "custom_parameter_error_report.md"
            with open(outmd, "w", encoding="utf-8") as f:
                f.write("# Custom Parameter Error Report\n\n")
                for line in lines:
                    f.write(f"- {line}")
            print(f"[INFO] エラーレポートを {outmd} に出力しました。")

    ans23 = input("エラーログを確認しますか？ [y/N]: ")
    if ans23.lower() == "y":
        show_error_log()

    # 追加: パラメータ依存関係自動検出機能
    def detect_parameter_dependencies():
        import glob, re, json
        files = sorted(glob.glob("custom_parameter_*.json"))
        if not files:
            print("[INFO] 依存関係を検出するテンプレートがありません。")
            return
        # すべてのパラメータ名一覧
        param_names = set()
        param_desc = {}
        param_opts = {}
        for fname in files:
            try:
                with open(fname, encoding="utf-8") as f:
                    data = json.load(f)
                n = data.get("name", fname)
                param_names.add(n)
                param_desc[n] = data.get("description", "")
                if data.get("type") == "select":
                    param_opts[n] = data.get("options", [])
            except Exception as e:
                continue
        dependencies = []
        # description/options内に他パラ名が含まれる場合は依存とみなす
        for n, desc in param_desc.items():
            for other in param_names:
                if other != n and other in desc:
                    dependencies.append((n, other, "description"))
        for n, opts in param_opts.items():
            for v in opts:
                for other in param_names:
                    if other != n and other in v:
                        dependencies.append((n, other, "options"))
        # avatar_config.jsonも参照（例: 条件付き有効化など）
        import os
        config_files = [f for f in os.listdir('.') if f.endswith('avatar_config.json')]
        for cfg in config_files:
            try:
                with open(cfg, encoding="utf-8") as f:
                    cfgdata = json.load(f)
                # 仮定: "dependencies": {"A": ["B", ...]} 形式
                deps = cfgdata.get("dependencies", {})
                for k, vlist in deps.items():
                    for v in vlist:
                        dependencies.append((k, v, f"{cfg} (config)"))
            except Exception as e:
                continue
        if not dependencies:
            print("[INFO] パラメータ間の依存関係は検出されませんでした。")
            return
        print("[SUMMARY] 検出されたパラメータ依存関係:")
        for n1, n2, src in dependencies:
            print(f"  {n1} → {n2}  (from {src})")
        print(f"[INFO] 依存関係総数: {len(dependencies)}")

    ans24 = input("パラメータ依存関係を自動検出しますか？ [y/N]: ")
    if ans24.lower() == "y":
        detect_parameter_dependencies()

    # 追加: 依存関係Markdownレポート出力機能
    def export_dependency_report():
        import glob, json, os
        files = sorted(glob.glob("custom_parameter_*.json"))
        if not files:
            print("[INFO] 依存関係レポート出力対象のテンプレートがありません。")
            return
        param_names = set()
        param_desc = {}
        param_opts = {}
        for fname in files:
            try:
                with open(fname, encoding="utf-8") as f:
                    data = json.load(f)
                n = data.get("name", fname)
                param_names.add(n)
                param_desc[n] = data.get("description", "")
                if data.get("type") == "select":
                    param_opts[n] = data.get("options", [])
            except Exception:
                continue
        dependencies = []
        for n, desc in param_desc.items():
            for other in param_names:
                if other != n and other in desc:
                    dependencies.append((n, other, "description"))
        for n, opts in param_opts.items():
            for v in opts:
                for other in param_names:
                    if other != n and other in v:
                        dependencies.append((n, other, "options"))
        config_files = [f for f in os.listdir('.') if f.endswith('avatar_config.json')]
        for cfg in config_files:
            try:
                with open(cfg, encoding="utf-8") as f:
                    cfgdata = json.load(f)
                deps = cfgdata.get("dependencies", {})
                for k, vlist in deps.items():
                    for v in vlist:
                        dependencies.append((k, v, f"{cfg} (config)"))
            except Exception:
                continue
        outmd = "custom_parameter_dependency_report.md"
        with open(outmd, "w", encoding="utf-8") as f:
            f.write("# Custom Parameter Dependency Report\n\n")
            if not dependencies:
                f.write("依存関係は検出されませんでした。\n")
            else:
                f.write("| From | To | Source |\n")
                f.write("|------|----|--------|\n")
                for n1, n2, src in dependencies:
                    f.write(f"| {n1} | {n2} | {src} |\n")
                f.write(f"\n依存関係総数: {len(dependencies)}\n")
        print(f"[INFO] 依存関係レポートを {outmd} に出力しました。")

    ans25 = input("依存関係をMarkdownレポートとして出力しますか？ [y/N]: ")
    if ans25.lower() == "y":
        export_dependency_report()

    # 追加: 依存関係DOTファイル出力機能
    def export_dependency_dot():
        import glob, json, os
        files = sorted(glob.glob("custom_parameter_*.json"))
        if not files:
            print("[INFO] DOTグラフ出力対象のテンプレートがありません。")
            return
        param_names = set()
        param_desc = {}
        param_opts = {}
        for fname in files:
            try:
                with open(fname, encoding="utf-8") as f:
                    data = json.load(f)
                n = data.get("name", fname)
                param_names.add(n)
                param_desc[n] = data.get("description", "")
                if data.get("type") == "select":
                    param_opts[n] = data.get("options", [])
            except Exception:
                continue
        edges = []
        for n, desc in param_desc.items():
            for other in param_names:
                if other != n and other in desc:
                    edges.append((n, other, "description"))
        for n, opts in param_opts.items():
            for v in opts:
                for other in param_names:
                    if other != n and other in v:
                        edges.append((n, other, "options"))
        config_files = [f for f in os.listdir('.') if f.endswith('avatar_config.json')]
        for cfg in config_files:
            try:
                with open(cfg, encoding="utf-8") as f:
                    cfgdata = json.load(f)
                deps = cfgdata.get("dependencies", {})
                for k, vlist in deps.items():
                    for v in vlist:
                        edges.append((k, v, "config"))
            except Exception:
                continue
        outdot = "custom_parameter_dependency_graph.dot"
        with open(outdot, "w", encoding="utf-8") as f:
            f.write("digraph CustomParameterDependencies {\n")
            f.write("    edge [penwidth=2];\n")
            f.write("    node [style=filled, fillcolor=white, fontname=Meiryo];\n")
            # ノード色分け: description=lightblue, options=lightgreen, config=lightpink, default=white
            node_types = {}
            for src, dst, typ in edges:
                node_types.setdefault(src, set()).add(typ)
                node_types.setdefault(dst, set()).add(typ)
            for n, types in node_types.items():
                if "config" in types:
                    color = "#ffe6e6"  # light pink
                elif "options" in types:
                    color = "#e6ffe6"  # light green
                elif "description" in types:
                    color = "#e6f0ff"  # light blue
                else:
                    color = "white"
                f.write(f'    "{n}" [fillcolor="{color}"];\n')
            for src, dst, typ in edges:
                color = "black"
                if typ == "description":
                    color = "#1f77b4"  # blue
                elif typ == "options":
                    color = "#2ca02c"  # green
                elif typ == "config":
                    color = "#d62728"  # red
                f.write(f'    "{src}" -> "{dst}" [color="{color}", label="{typ}"];\n')
            f.write("}\n")
        print(f"[INFO] 依存関係グラフを {outdot} に出力しました。")

    ans26 = input("依存関係グラフをDOTファイル(Graphviz)で出力しますか？ [y/N]: ")
    if ans26.lower() == "y":
        export_dependency_dot()

    # 追加: DOTファイルからPNG画像生成（Graphviz）
    def export_dot_to_png():
        import subprocess, os
        dotfile = "custom_parameter_dependency_graph.dot"
        pngfile = "custom_parameter_dependency_graph.png"
        if not os.path.exists(dotfile):
            print(f"[ERROR] {dotfile} が存在しません。まずDOTファイルを出力してください。")
            return
        try:
            subprocess.run(["dot", "-Tpng", dotfile, "-o", pngfile], check=True)
            print(f"[INFO] 依存関係グラフ画像を {pngfile} に出力しました。")
        except FileNotFoundError:
            print("[ERROR] Graphviz(dotコマンド)が見つかりません。インストールしてください。")
        except Exception as e:
            print(f"[ERROR] PNG画像生成失敗: {e}")

    ans27 = input("DOTファイルから依存関係グラフ画像(PNG)を生成しますか？ [y/N]: ")
    if ans27.lower() == "y":
        export_dot_to_png()

    # 追加: DOTファイルからSVG画像生成（Graphviz）
    def export_dot_to_svg():
        import subprocess, os
        dotfile = "custom_parameter_dependency_graph.dot"
        svgfile = "custom_parameter_dependency_graph.svg"
        if not os.path.exists(dotfile):
            print(f"[ERROR] {dotfile} が存在しません。まずDOTファイルを出力してください。")
            return
        try:
            subprocess.run(["dot", "-Tsvg", dotfile, "-o", svgfile], check=True)
            print(f"[INFO] 依存関係グラフ画像(SVG)は依存タイプごとに色分けされています: {svgfile}")
        except FileNotFoundError:
            print("[ERROR] Graphviz(dotコマンド)が見つかりません。インストールしてください。")
        except Exception as e:
            print(f"[ERROR] SVG画像生成失敗: {e}")

    ans28 = input("DOTファイルから依存関係グラフ画像(SVG)を生成しますか？ [y/N]: ")
    if ans28.lower() == "y":
        export_dot_to_svg()

    # 追加: パラメータ循環依存検出機能
    def detect_circular_dependencies():
        import glob, json, os
        files = sorted(glob.glob("custom_parameter_*.json"))
        if not files:
            print("[INFO] 循環依存チェック対象のテンプレートがありません。")
            return
        param_names = set()
        param_desc = {}
        param_opts = {}
        for fname in files:
            try:
                with open(fname, encoding="utf-8") as f:
                    data = json.load(f)
                n = data.get("name", fname)
                param_names.add(n)
                param_desc[n] = data.get("description", "")
                if data.get("type") == "select":
                    param_opts[n] = data.get("options", [])
            except Exception:
                continue
        edges = []
        for n, desc in param_desc.items():
            for other in param_names:
                if other != n and other in desc:
                    edges.append((n, other))
        for n, opts in param_opts.items():
            for v in opts:
                for other in param_names:
                    if other != n and other in v:
                        edges.append((n, other))
        config_files = [f for f in os.listdir('.') if f.endswith('avatar_config.json')]
        for cfg in config_files:
            try:
                with open(cfg, encoding="utf-8") as f:
                    cfgdata = json.load(f)
                deps = cfgdata.get("dependencies", {})
                for k, vlist in deps.items():
                    for v in vlist:
                        edges.append((k, v))
            except Exception:
                continue
        # グラフ巡回で循環検出
        from collections import defaultdict, deque
        graph = defaultdict(list)
        for src, dst in edges:
            graph[src].append(dst)
        cycles = []
        def dfs(node, path, visited):
            if node in path:
                idx = path.index(node)
                cycle = path[idx:] + [node]
                if cycle not in cycles:
                    cycles.append(cycle)
                return
            visited.add(node)
            for neighbor in graph.get(node, []):
                dfs(neighbor, path + [node], visited)
            visited.remove(node)
        for n in param_names:
            dfs(n, [], set())
        if not cycles:
            print("[INFO] パラメータ間に循環依存は検出されませんでした。")
        else:
            print("[WARNING] 循環依存が検出されました:")
            for cyc in cycles:
                print("  → ".join(cyc))
            print(f"[INFO] 循環依存の総数: {len(cycles)}")

    ans26 = input("パラメータ循環依存をチェックしますか？ [y/N]: ")
    if ans26.lower() == "y":
        detect_circular_dependencies()

    # 追加: 依存関係グラフDOTファイル出力機能
    def export_dependency_dot():
        import glob, json, os
        files = sorted(glob.glob("custom_parameter_*.json"))
        if not files:
            print("[INFO] DOTグラフ出力対象のテンプレートがありません。")
            return
        param_names = set()
        param_desc = {}
        param_opts = {}
        for fname in files:
            try:
                with open(fname, encoding="utf-8") as f:
                    data = json.load(f)
                n = data.get("name", fname)
                param_names.add(n)
                param_desc[n] = data.get("description", "")
                if data.get("type") == "select":
                    param_opts[n] = data.get("options", [])
            except Exception:
                continue
        edges = []
        for n, desc in param_desc.items():
            for other in param_names:
                if other != n and other in desc:
                    edges.append((n, other))
        for n, opts in param_opts.items():
            for v in opts:
                for other in param_names:
                    if other != n and other in v:
                        edges.append((n, other))
        config_files = [f for f in os.listdir('.') if f.endswith('avatar_config.json')]
        for cfg in config_files:
            try:
                with open(cfg, encoding="utf-8") as f:
                    cfgdata = json.load(f)
                deps = cfgdata.get("dependencies", {})
                for k, vlist in deps.items():
                    for v in vlist:
                        edges.append((k, v))
            except Exception:
                continue
        outdot = "custom_parameter_dependency_graph.dot"
        with open(outdot, "w", encoding="utf-8") as f:
            f.write("digraph CustomParameterDependencies {\n")
            for src, dst in edges:
                f.write(f'    "{src}" -> "{dst}";\n')
            f.write("}\n")
        print(f"[INFO] 依存関係グラフを {outdot} に出力しました。")

    ans27 = input("依存関係グラフをDOTファイル(Graphviz)で出力しますか？ [y/N]: ")
    if ans27.lower() == "y":
        export_dependency_dot()

    # 追加: DOTファイルからPNG画像生成（Graphviz）
    def export_dot_to_png():
        import subprocess, os
        dotfile = "custom_parameter_dependency_graph.dot"
        pngfile = "custom_parameter_dependency_graph.png"
        if not os.path.exists(dotfile):
            print(f"[ERROR] {dotfile} が存在しません。まずDOTファイルを出力してください。")
            return
        try:
            subprocess.run(["dot", "-Tpng", dotfile, "-o", pngfile], check=True)
            print(f"[INFO] 依存関係グラフ画像を {pngfile} に出力しました。")
        except FileNotFoundError:
            print("[ERROR] Graphviz(dotコマンド)が見つかりません。インストールしてください。")
        except Exception as e:
            print(f"[ERROR] PNG画像生成失敗: {e}")

    ans28 = input("DOTファイルから依存関係グラフ画像(PNG)を生成しますか？ [y/N]: ")
    if ans28.lower() == "y":
        export_dot_to_png()

    # 追加: DOTファイルからSVG画像生成（Graphviz）
    def export_dot_to_svg():
        import subprocess, os
        dotfile = "custom_parameter_dependency_graph.dot"
        svgfile = "custom_parameter_dependency_graph.svg"
        if not os.path.exists(dotfile):
            print(f"[ERROR] {dotfile} が存在しません。まずDOTファイルを出力してください。")
            return
        try:
            subprocess.run(["dot", "-Tsvg", dotfile, "-o", svgfile], check=True)
            print(f"[INFO] 依存関係グラフ画像(SVG)は依存タイプごとに色分けされています: {svgfile}")
        except FileNotFoundError:
            print("[ERROR] Graphviz(dotコマンド)が見つかりません。インストールしてください。")
        except Exception as e:
            print(f"[ERROR] SVG画像生成失敗: {e}")

    ans29 = input("DOTファイルから依存関係グラフ画像(SVG)を生成しますか？ [y/N]: ")
    if ans29.lower() == "y":
        export_dot_to_svg()
