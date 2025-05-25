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
        if not os.path.exists(self.history_file):
            return
        with open(self.history_file, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                if (preset_name is None) or (entry["preset_name"] == preset_name):
                    yield entry

    def print_history(self, preset_name=None):
        for entry in self.iter_history(preset_name):
            ts = datetime.fromtimestamp(entry["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] {entry['preset_name']} {entry['change_type']}: {entry['note']}")

if __name__ == "__main__":
    # サンプル利用例
    hist = PresetChangeHistory()
    before = {"name": "A", "param": 1}
    after = {"name": "A", "param": 2}
    hist.record_change("A", "edit", before, after, user="admin", note="パラメータ変更")
    hist.record_change("A", "validate", after, after, user="system", note="バリデーションOK")
    print("履歴:")
    hist.print_history("A")
