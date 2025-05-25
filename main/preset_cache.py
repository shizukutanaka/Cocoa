import json
import os
from typing import Dict, List

import threading
import time

class PresetCache:
    def __init__(self, preset_dir: str, auto_reload: bool = True, reload_interval: int = 2):
        self.preset_dir = preset_dir
        self.cache: Dict[str, dict] = {}
        self.mtime_map: Dict[str, float] = {}
        self.lock = threading.Lock()
        self.last_reload = 0
        self.reload_interval = reload_interval
        self.auto_reload = auto_reload
        self._stop_event = threading.Event()
        self._watcher_thread = None
        self.load_cache()
        if self.auto_reload:
            self._start_watcher()

    def load_cache(self):
        with self.lock:
            self.cache.clear()
            self.mtime_map.clear()
            for fname in os.listdir(self.preset_dir):
                if fname.endswith('.json'):
                    path = os.path.join(self.preset_dir, fname)
                    try:
                        mtime = os.path.getmtime(path)
                        with open(path, 'r', encoding='utf-8') as f:
                            self.cache[fname] = json.load(f)
                        self.mtime_map[fname] = mtime
                    except Exception as e:
                        print(f"[WARN] Failed to load {fname}: {e}")

    def get_preset(self, name: str) -> dict:
        self._maybe_reload()
        with self.lock:
            return self.cache.get(name)

    def search_presets(self, keyword: str) -> List[str]:
        self._maybe_reload()
        with self.lock:
            return [k for k, v in self.cache.items() if keyword.lower() in json.dumps(v, ensure_ascii=False).lower()]

    def refresh(self):
        self.load_cache()

    def _maybe_reload(self):
        now = time.time()
        if now - self.last_reload < self.reload_interval:
            return
        changed = False
        for fname in os.listdir(self.preset_dir):
            if fname.endswith('.json'):
                path = os.path.join(self.preset_dir, fname)
                try:
                    mtime = os.path.getmtime(path)
                    if fname not in self.mtime_map or self.mtime_map[fname] != mtime:
                        changed = True
                        break
                except Exception as e:
                    print(f"[WARN] Failed to stat {fname}: {e}")
        if changed:
            self.load_cache()
            self.last_reload = now

    def _start_watcher(self):
        def watch():
            while not self._stop_event.is_set():
                try:
                    self._maybe_reload()
                except Exception as e:
                    print(f"[ERROR] Watcher exception: {e}")
                time.sleep(self.reload_interval)
        self._watcher_thread = threading.Thread(target=watch, daemon=True)
        self._watcher_thread.start()

    def stop(self):
        self._stop_event.set()
        if self._watcher_thread:
            self._watcher_thread.join()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Satin Preset Cache Tool")
    subparsers = parser.add_subparsers(dest="command")

    parser.add_argument("preset_dir", help="Preset directory")

    search_parser = subparsers.add_parser("search", help="Search presets by keyword")
    search_parser.add_argument("keyword")

    list_parser = subparsers.add_parser("list", help="List all cached presets")

    show_parser = subparsers.add_parser("show", help="Show preset content")
    show_parser.add_argument("preset_name")

    refresh_parser = subparsers.add_parser("refresh", help="Manually refresh cache")

    stop_parser = subparsers.add_parser("stop", help="Stop cache watcher thread")

    args = parser.parse_args()
    cache = PresetCache(args.preset_dir)

    if args.command == "search":
        matches = cache.search_presets(args.keyword)
        print(f"Found {len(matches)} presets:")
        for m in matches:
            print(m)
    elif args.command == "list":
        print(f"Cached presets ({len(cache.cache)}):")
        for k in cache.cache.keys():
            print(k)
    elif args.command == "show":
        preset = cache.get_preset(args.preset_name)
        if preset:
            print(json.dumps(preset, ensure_ascii=False, indent=2))
        else:
            print(f"Preset not found: {args.preset_name}")
    elif args.command == "refresh":
        cache.refresh()
        print("Cache refreshed.")
    elif args.command == "stop":
        cache.stop()
        print("Watcher stopped.")
    else:
        parser.print_help()
