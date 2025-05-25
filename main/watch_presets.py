import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import argparse
import os

class PresetChangeHandler(FileSystemEventHandler):
    def __init__(self, presets_dir, out_dir):
        self.presets_dir = presets_dir
        self.out_dir = out_dir
    def on_any_event(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith('.json'):
            print(f"[INFO] Change detected: {event.src_path}. Running automation...")
            subprocess.run(["python", "manage_satin.py", "validate", "--presets", self.presets_dir, "--out", self.out_dir])
            subprocess.run(["python", "manage_satin.py", "tag", "--presets", self.presets_dir, "--out", self.out_dir])
            subprocess.run(["python", "manage_satin.py", "dependency", "--presets", self.presets_dir, "--out", self.out_dir])
            print(f"[INFO] Automation complete.")

def main():
    parser = argparse.ArgumentParser(description="Satin Preset Directory Watcher & Auto-Validator")
    parser.add_argument("--presets", default="./presets", help="Preset directory to watch")
    parser.add_argument("--out", default="./out", help="Output directory for reports/tags")
    args = parser.parse_args()

    event_handler = PresetChangeHandler(args.presets, args.out)
    observer = Observer()
    observer.schedule(event_handler, args.presets, recursive=True)
    observer.start()
    print(f"[INFO] Watching {args.presets} for changes. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
