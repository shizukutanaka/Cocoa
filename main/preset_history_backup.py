import os
import time
import shutil
from datetime import datetime, timedelta
import argparse

def backup_history(history_file, backup_dir='history_backups', max_backups=7, max_days=30):
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f"{os.path.basename(history_file)}.{ts}.bak")
    shutil.copy2(history_file, backup_path)
    # 古いバックアップ削除（世代超過 or 日数超過）
    backups = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith(os.path.basename(history_file))])
    # 世代数超過
    if len(backups) > max_backups:
        for old in backups[:-max_backups]:
            try:
                os.remove(old)
            except Exception:
                pass
    # 日数超過
    now = datetime.now()
    for b in backups:
        try:
            t = datetime.fromtimestamp(os.path.getmtime(b))
            if (now - t).days > max_days:
                os.remove(b)
        except Exception:
            pass
    print(f"バックアップ: {backup_path}")

def monitor_and_backup(history_file, backup_dir, max_backups, max_days, interval):
    print(f"{history_file} を{interval//60}分ごとにバックアップ 最大{max_backups}世代/{max_days}日保存")
    while True:
        try:
            backup_history(history_file, backup_dir, max_backups, max_days)
        except Exception as e:
            print(f"バックアップエラー: {e}")
        time.sleep(interval)

def main():
    parser = argparse.ArgumentParser(description='プリセット履歴自動バックアップ')
    parser.add_argument('history_file', help='監視対象履歴ファイル')
    parser.add_argument('--backup_dir', default='history_backups', help='バックアップ保存先')
    parser.add_argument('--max_backups', type=int, default=7, help='最大世代数')
    parser.add_argument('--max_days', type=int, default=30, help='保存日数')
    parser.add_argument('--interval', type=int, default=3600, help='バックアップ間隔(秒)')
    args = parser.parse_args()
    monitor_and_backup(args.history_file, args.backup_dir, args.max_backups, args.max_days, args.interval)

if __name__ == '__main__':
    main()
