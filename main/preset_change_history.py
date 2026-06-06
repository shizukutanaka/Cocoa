import json
import os
import time
from datetime import datetime

class PresetChangeHistory:
    def __init__(self, history_file="preset_change_history.jsonl"):
        self.history_file = history_file
        os.makedirs(os.path.dirname(history_file) or '.', exist_ok=True)

    def record_change(self, preset_name, change_type, before, after, user=None, note=None):
        entry = {
            "timestamp": time.time(),
            "preset_name": preset_name,
            "change_type": change_type,  # 'edit', 'validate', 'apply', etc
            "before": before,
            "after": after,
            "user": user,
            "note": note
        }
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def iter_history(self, preset_name=None):
        """履歴を反復する。空行と壊れた(JSON不正な)行はスキップする。REQ-PH-03。"""
        if not os.path.exists(self.history_file):
            return
        with open(self.history_file, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue  # 壊れた行はスキップ（反復全体をクラッシュさせない）
                if (preset_name is None) or (entry.get("preset_name") == preset_name):
                    yield entry

    def get_history(self, preset_name=None):
        """履歴を materialize したリストで返す。REQ-PH-04。"""
        return list(self.iter_history(preset_name))

    def count(self, preset_name=None):
        """履歴件数を返す。REQ-PH-04。"""
        return sum(1 for _ in self.iter_history(preset_name))

    def latest_state(self, preset_name=None):
        """最後のエントリの after 状態を返す。履歴が無ければ None。REQ-PH-05。"""
        last = None
        for entry in self.iter_history(preset_name):
            last = entry
        return last["after"] if last is not None else None

    def get_version(self, preset_name, index):
        """時系列 index（負可）の after 状態を返す。履歴無しは IndexError。REQ-PH-06。"""
        entries = self.get_history(preset_name)
        if not entries:
            raise IndexError(f"no history for preset: {preset_name!r}")
        return entries[index]["after"]  # index 範囲外は IndexError

    def rollback(self, preset_name, index, user=None, note=None):
        """指定バージョンの after 状態へロールバックする。REQ-PH-07。

        対象状態を返し、change_type='rollback' のエントリを追記する
        （before=現在の最新 after, after=対象状態）。
        """
        entries = self.get_history(preset_name)
        if not entries:
            raise IndexError(f"no history for preset: {preset_name!r}")
        target = entries[index]["after"]
        current = entries[-1]["after"]
        self.record_change(
            preset_name, "rollback", before=current, after=target,
            user=user, note=note or f"rollback to #{index}",
        )
        return target

    def print_history(self, preset_name=None):
        for entry in self.iter_history(preset_name):
            ts = datetime.fromtimestamp(entry["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] {entry['preset_name']} {entry['change_type']}: {entry.get('note')}")

if __name__ == "__main__":
    # サンプル利用例
    hist = PresetChangeHistory()
    before = {"name": "A", "param": 1}
    after = {"name": "A", "param": 2}
    hist.record_change("A", "edit", before, after, user="admin", note="パラメータ変更")
    hist.record_change("A", "validate", after, after, user="system", note="バリデーションOK")
    print("履歴:")
    hist.print_history("A")
