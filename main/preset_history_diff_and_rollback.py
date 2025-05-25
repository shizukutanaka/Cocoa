import json
import argparse
from datetime import datetime
from preset_change_history import PresetChangeHistory

def diff_dict(d1, d2):
    """シンプルなdict差分表示"""
    keys = set(d1.keys()) | set(d2.keys())
    diffs = []
    for k in sorted(keys):
        v1 = d1.get(k)
        v2 = d2.get(k)
        if v1 != v2:
            diffs.append(f"{k}: {v1} -> {v2}")
    return diffs

def find_entry_by_time(entries, ts):
    # ts: 'YYYY-mm-dd HH:MM:SS' 形式
    target = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").timestamp()
    closest = None
    for e in entries:
        if closest is None or abs(e['timestamp'] - target) < abs(closest['timestamp'] - target):
            closest = e
    return closest

def main():
    parser = argparse.ArgumentParser(description="プリセット履歴差分比較・ロールバック")
    parser.add_argument("preset", help="プリセット名")
    parser.add_argument("--from_time", help="比較元時刻(YYYY-mm-dd HH:MM:SS)")
    parser.add_argument("--to_time", help="比較先時刻(YYYY-mm-dd HH:MM:SS)")
    parser.add_argument("--rollback", help="ロールバック先時刻(YYYY-mm-dd HH:MM:SS)")
    parser.add_argument("--out", help="ロールバックJSON出力先")
    args = parser.parse_args()
    hist = PresetChangeHistory()
    entries = list(hist.iter_history(args.preset))
    if args.from_time and args.to_time:
        e1 = find_entry_by_time(entries, args.from_time)
        e2 = find_entry_by_time(entries, args.to_time)
        print(f"[{args.from_time}] -> [{args.to_time}] の差分:")
        for diff in diff_dict(e1['after'], e2['after']):
            print(diff)
    elif args.rollback:
        e = find_entry_by_time(entries, args.rollback)
        if not e:
            print("指定時刻の履歴が見つかりません")
            return
        outpath = args.out or f"rollback_{args.preset}.json"
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump(e['after'], f, ensure_ascii=False, indent=2)
        print(f"{args.preset}を{args.rollback}時点にロールバック: {outpath}")
    else:
        print("--from_time/--to_timeで差分比較、--rollbackでロールバックが可能です")

if __name__ == "__main__":
    main()
