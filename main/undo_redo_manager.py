import json
import os
from typing import Any, List

import threading
import shutil
import logging

class UndoRedoManager:
    def __init__(self, history_file: str, max_history: int = 20):
        self.history_file = history_file
        self.backup_file = history_file + '.bak'
        self.max_history = max_history
        self.history: List[Any] = []
        self.index = -1
        self.lock = threading.Lock()
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history = data.get('history', [])
                    self.index = data.get('index', -1)
        except Exception as e:
            logging.warning(f"[WARN] Failed to load history file: {e}. Trying backup...")
            # 自動リカバリ: バックアップから復元
            if os.path.exists(self.backup_file):
                try:
                    with open(self.backup_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.history = data.get('history', [])
                        self.index = data.get('index', -1)
                        logging.info("[INFO] History recovered from backup.")
                except Exception as e2:
                    logging.error(f"[ERROR] Failed to recover from backup: {e2}")
            else:
                self.history = []
                self.index = -1

    def _save(self):
        with self.lock:
            # 直前にバックアップを保存
            if os.path.exists(self.history_file):
                try:
                    shutil.copy2(self.history_file, self.backup_file)
                except Exception as e:
                    logging.warning(f"[WARN] Backup failed: {e}")
            try:
                with open(self.history_file, 'w', encoding='utf-8') as f:
                    json.dump({'history': self.history, 'index': self.index}, f)
                    f.flush()
                    os.fsync(f.fileno())
            except Exception as e:
                logging.error(f"[ERROR] Failed to save history: {e}")

    def add_state(self, state: Any):
        with self.lock:
            # 直近の状態以降は削除
            self.history = self.history[:self.index+1]
            self.history.append(state)
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]
            self.index = len(self.history) - 1
            self._save()

    def undo(self) -> Any:
        with self.lock:
            if self.index > 0:
                self.index -= 1
                self._save()
                return self.history[self.index]
            return None

    def redo(self) -> Any:
        with self.lock:
            if self.index < len(self.history) - 1:
                self.index += 1
                self._save()
                return self.history[self.index]
            return None

# サンプルCLI
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Undo/Redo Manager CLI")
    parser.add_argument("history_file", help="履歴ファイルパス")
    parser.add_argument("command", choices=["add", "undo", "redo"])
    parser.add_argument("--state", help="追加する状態(JSON文字列)")
    args = parser.parse_args()
    mgr = UndoRedoManager(args.history_file)
    if args.command == "add" and args.state:
        try:
            state = json.loads(args.state)
        except Exception:
            print("[ERROR] JSON形式で入力してください")
            exit(1)
        mgr.add_state(state)
        print("[INFO] 状態追加")
    elif args.command == "undo":
        state = mgr.undo()
        print(json.dumps(state, ensure_ascii=False, indent=2))
    elif args.command == "redo":
        state = mgr.redo()
        print(json.dumps(state, ensure_ascii=False, indent=2))
