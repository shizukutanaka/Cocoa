import json
import os
from typing import Dict, Set

def collect_dependencies(preset: dict, dependency_keys=None) -> Set[str]:
    if dependency_keys is None:
        dependency_keys = ["base_preset", "inherits", "reference"]
    deps = set()
    for key in dependency_keys:
        val = preset.get(key)
        if isinstance(val, str):
            deps.add(val)
        elif isinstance(val, list):
            deps.update([v for v in val if isinstance(v, str)])
    return deps

import time
import logging

def analyze_all_dependencies(preset_dir: str, dependency_keys=None, show_progress=True, retry=2) -> Dict[str, Set[str]]:
    result = {}
    files = [f for f in os.listdir(preset_dir) if f.endswith('.json')]
    total = len(files)
    for idx, fname in enumerate(files, 1):
        for attempt in range(retry):
            try:
                with open(os.path.join(preset_dir, fname), 'r', encoding='utf-8') as f:
                    preset = json.load(f)
                deps = collect_dependencies(preset, dependency_keys)
                if deps:
                    result[fname] = deps
                break
            except Exception as e:
                logging.warning(f"[WARN] Failed to load {fname}: {e}")
                time.sleep(0.2)
        if show_progress and (idx % 10 == 0 or idx == total):
            print(f"[{idx}/{total}] analyzed...")
    return result

def invert_dependencies(dep_map: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    """依存マップの逆引き辞書を作成する"""
    inv: Dict[str, Set[str]] = {}
    for src, targets in dep_map.items():
        for t in targets:
            inv.setdefault(t, set()).add(src)
    return inv

def find_isolated_presets(dep_map: Dict[str, Set[str]], all_files: Set[str]) -> Set[str]:
    """他から参照されていない孤立プリセットを抽出する"""
    referenced: Set[str] = set()
    for targets in dep_map.values():
        referenced.update(targets)
    return set(all_files) - referenced - set(dep_map.keys())

def detect_cycles(dep_map: Dict[str, Set[str]]) -> Set[tuple]:
    """循環依存(ループ)を検出し、サイクルのタプル集合を返す"""
    cycles = set()
    visited = set()
    def visit(node, path):
        if node in path:
            cycle = tuple(path[path.index(node):] + [node])
            cycles.add(cycle)
            return
        if node in visited:
            return
        visited.add(node)
        for neighbor in dep_map.get(node, []):
            visit(neighbor, path + [node])
    for n in dep_map:
        visit(n, [])
    return cycles

def max_dependency_depth(dep_map: Dict[str, Set[str]]) -> int:
    """依存関係の最大深度を計算する"""
    memo = {}
    def depth(node):
        if node in memo:
            return memo[node]
        children = dep_map.get(node, set())
        if not children:
            memo[node] = 1
            return 1
        d = 1 + max(depth(c) for c in children if c != node)
        memo[node] = d
        return d
    return max((depth(n) for n in dep_map), default=0)

def dependency_summary(dep_map: Dict[str, Set[str]]) -> dict:
    """依存数・被依存数などの統計を返す"""
    inv = invert_dependencies(dep_map)
    out = {
        'total_presets': len(dep_map),
        'max_dependencies': max((len(v) for v in dep_map.values()), default=0),
        'max_dependents': max((len(v) for v in inv.values()), default=0),
        'max_depth': max_dependency_depth(dep_map),
    }
    return out

def all_ancestors(dep_map: Dict[str, Set[str]], node: str, memo=None) -> Set[str]:
    """指定ノードの全祖先（依存元）を再帰的に列挙する"""
    if memo is None:
        memo = {}
    if node in memo:
        return memo[node]
    ancestors = set()
    for parent in invert_dependencies(dep_map).get(node, set()):
        ancestors.add(parent)
        ancestors.update(all_ancestors(dep_map, parent, memo))
    memo[node] = ancestors
    return ancestors

def all_descendants(dep_map: Dict[str, Set[str]], node: str, memo=None) -> Set[str]:
    """指定ノードの全子孫（依存先）を再帰的に列挙する"""
    if memo is None:
        memo = {}
    if node in memo:
        return memo[node]
    descendants = set()
    for child in dep_map.get(node, set()):
        descendants.add(child)
        descendants.update(all_descendants(dep_map, child, memo))
    memo[node] = descendants
    return descendants

def extract_subgraph(dep_map: Dict[str, Set[str]], start: str) -> Dict[str, Set[str]]:
    """指定ノードから辿れる依存サブグラフを抽出する"""
    sub = {}
    to_visit = {start}
    seen = set()
    while to_visit:
        n = to_visit.pop()
        if n in seen:
            continue
        seen.add(n)
        children = dep_map.get(n, set())
        if children:
            sub[n] = set(children)
            to_visit.update(children)
    return sub

def save_dot_graph(dep_map: Dict[str, Set[str]], out_path: str) -> None:
    """
    dot形式で依存グラフを書き出し。
    out_pathが.pngや.jpgならgraphvizで画像も自動生成。
    """
    import os
    dot_path = out_path
    if out_path.lower().endswith(('.png', '.jpg', '.jpeg', '.svg')):
        dot_path = out_path + '.dot'
    with open(dot_path, 'w', encoding='utf-8') as f:
        f.write('digraph dependencies {\n')
        for src, targets in dep_map.items():
            for t in targets:
                f.write(f'  "{src}" -> "{t}";\n')
        f.write('}\n')
    print(f"DOT graph saved: {dot_path}")
    # 画像生成
    if out_path.lower().endswith(('.png', '.jpg', '.jpeg', '.svg')):
        try:
            import subprocess
            fmt = os.path.splitext(out_path)[1][1:]
            subprocess.run(['dot', f'-T{fmt}', dot_path, '-o', out_path], check=True)
            print(f"Dependency graph image saved: {out_path}")
        except Exception as e:
            print(f"[WARN] Could not generate image: {e}")

def save_dependency_csv(dep_map: Dict[str, Set[str]], out_path: str):
    """依存関係をCSV形式で保存"""
    import csv
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['preset', 'depends_on'])
        for src, targets in dep_map.items():
            for t in targets:
                writer.writerow([src, t])
    print(f"Dependency CSV saved: {out_path}")

def print_dependency_table(dep_map: Dict[str, Set[str]]):
    """依存関係をテーブル形式で標準出力に表示"""
    from tabulate import tabulate
    rows = []
    for src, targets in dep_map.items():
        if targets:
            for t in targets:
                rows.append([src, t])
        else:
            rows.append([src, ''])
    print(tabulate(rows, headers=['preset', 'depends_on'], tablefmt='github'))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Satin Preset Dependency Analyzer")
    parser.add_argument("preset_dir", help="Preset directory")
    parser.add_argument("out_report", help="Output dependency report JSON")
    parser.add_argument("--keys", nargs="*", default=None, help="Dependency keys (default: base_preset, inherits, reference)")
    parser.add_argument("--dot", help="Save dependency graph as dot file")
    parser.add_argument("--inverse", action="store_true", help="Show inverse dependency map")
    parser.add_argument("--isolated", action="store_true", help="Show isolated presets")
    parser.add_argument("--cycles", action="store_true", help="Detect and show dependency cycles")
    parser.add_argument("--depth", action="store_true", help="Show max dependency depth")
    parser.add_argument("--summary", action="store_true", help="Show dependency summary")
    parser.add_argument("--ancestors", help="Show all ancestors (dependencies) of the given preset name")
    parser.add_argument("--descendants", help="Show all descendants (dependents) of the given preset name")
    parser.add_argument("--subgraph", help="Extract and print subgraph from the given preset name")
    parser.add_argument("--csv", help="Save dependency CSV file")
    parser.add_argument("--table", action="store_true", help="Print dependency table to stdout")
    parser.add_argument("--log", help="Log file for errors/progress")
    args = parser.parse_args()
    if args.log:
        logging.basicConfig(filename=args.log, level=logging.INFO)
    else:
        logging.basicConfig(level=logging.INFO)
    t0 = time.time()
    report = analyze_all_dependencies(args.preset_dir, args.keys)
    save_dependency_report(report, args.out_report)
    t1 = time.time()
    print(f"Analyzed {len(report)} presets in {t1-t0:.2f}s")
    if args.dot:
        save_dot_graph(report, args.dot)
    if args.inverse:
        inv = invert_dependencies(report)
        print("Inverse dependency map:")
        for k, v in inv.items():
            print(f"{k}: {sorted(v)}")
    if args.isolated:
        all_files = set([f for f in os.listdir(args.preset_dir) if f.endswith('.json')])
        iso = find_isolated_presets(report, all_files)
        print("Isolated presets:")
        for f in sorted(iso):
            print(f)
    if args.cycles:
        cycles = detect_cycles(report)
        print(f"Cycles ({len(cycles)}):")
        for cyc in sorted(cycles):
            print(" -> ".join(cyc))
    if args.depth:
        print(f"Max dependency depth: {max_dependency_depth(report)}")
    if args.summary:
        print("Dependency summary:")
        for k, v in dependency_summary(report).items():
            print(f"  {k}: {v}")
    if args.ancestors:
        node = args.ancestors
        if node not in report:
            print(f"{node} not found in dependency map.")
        else:
            ancestors = all_ancestors(report, node)
            print(f"Ancestors of {node}: {sorted(ancestors)}")
    if args.descendants:
        node = args.descendants
        if node not in report:
            print(f"{node} not found in dependency map.")
        else:
            descendants = all_descendants(report, node)
            print(f"Descendants of {node}: {sorted(descendants)}")
    if args.subgraph:
        node = args.subgraph
        if node not in report:
            print(f"{node} not found in dependency map.")
        else:
            sub = extract_subgraph(report, node)
            print(f"Subgraph from {node}:")
            for k, v in sub.items():
                print(f"  {k}: {sorted(v)}")
    if args.csv:
        save_dependency_csv(report, args.csv)
    if args.table:
        try:
            print_dependency_table(report)
        except ImportError:
            print("[ERROR] 'tabulate' package is required for --table output. Please install with 'pip install tabulate'.")
