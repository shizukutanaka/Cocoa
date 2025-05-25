import os
import json
import glob
import argparse
from collections import defaultdict

def extract_dependencies(preset):
    """
    プリセットJSONから依存先プリセット名リストを抽出
    例: {"name": "A", "depends_on": ["B", "C"]}
    """
    deps = preset.get("depends_on", [])
    if isinstance(deps, str):
        deps = [deps]
    return deps

def build_dependency_graph(target_dir):
    graph = defaultdict(list)
    name_map = {}
    for path in glob.glob(os.path.join(target_dir, "*.json")):
        with open(path, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                continue
            name = data.get("name") or os.path.splitext(os.path.basename(path))[0]
            name_map[path] = name
            deps = extract_dependencies(data)
            for dep in deps:
                graph[name].append(dep)
    return graph

def write_dot(graph, out_path):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("digraph PresetDeps {\n")
        for src, tgts in graph.items():
            for tgt in tgts:
                f.write(f'  "{src}" -> "{tgt}";\n')
        f.write("}\n")

def main():
    parser = argparse.ArgumentParser(description="プリセット依存関係グラフ化ツール")
    parser.add_argument("dir", help="プリセットjson格納ディレクトリ")
    parser.add_argument("--dot", default="preset_deps.dot", help="dotファイル出力先")
    parser.add_argument("--png", default=None, help="GraphvizでPNG画像も生成")
    args = parser.parse_args()
    graph = build_dependency_graph(args.dir)
    write_dot(graph, args.dot)
    print(f"dotファイルを出力: {args.dot}")
    if args.png:
        import subprocess
        try:
            subprocess.run(["dot", "-Tpng", args.dot, "-o", args.png], check=True)
            print(f"PNG画像を出力: {args.png}")
        except Exception as e:
            print(f"Graphviz実行エラー: {e}")

if __name__ == "__main__":
    main()
