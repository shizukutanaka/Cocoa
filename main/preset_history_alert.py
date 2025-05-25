import time
import json
import requests
import argparse
from datetime import datetime
from preset_change_history import PresetChangeHistory

def send_slack_alert(webhook_url, message):
    payload = {"text": message}
    try:
        r = requests.post(webhook_url, json=payload, timeout=5)
        r.raise_for_status()
    except Exception as e:
        print(f"Slack通知失敗: {e}")

def monitor_history(history_file, webhook_url, poll_interval=10):
    print(f"プリセット履歴監視開始: {history_file}")
    seen = set()
    hist = PresetChangeHistory(history_file)
    while True:
        try:
            for entry in hist.iter_history():
                key = (entry['timestamp'], entry['preset_name'], entry['change_type'])
                if key in seen:
                    continue
                seen.add(key)
                # 異常検知例: バリデーション失敗や頻繁なロールバック
                if entry['change_type'] == 'validate' and 'error' in (entry.get('note') or '').lower():
                    ts = datetime.fromtimestamp(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                    msg = f"[Cocoa履歴異常] {ts} {entry['preset_name']} バリデーションエラー\n{entry.get('note')}"
                    send_slack_alert(webhook_url, msg)
                if entry['change_type'] == 'rollback':
                    ts = datetime.fromtimestamp(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                    msg = f"[Cocoa履歴異常] {ts} {entry['preset_name']} ロールバック実行\n{entry.get('note')}"
                    send_slack_alert(webhook_url, msg)
        except Exception as e:
            print(f"履歴監視エラー: {e}")
        time.sleep(poll_interval)

def main():
    parser = argparse.ArgumentParser(description='プリセット履歴異常検知＆Slack通知')
    parser.add_argument('history_file', help='監視対象履歴ファイル')
    parser.add_argument('--slack', required=True, help='Slack Incoming Webhook URL')
    parser.add_argument('--interval', type=int, default=10, help='監視間隔(秒)')
    args = parser.parse_args()
    monitor_history(args.history_file, args.slack, args.interval)

if __name__ == '__main__':
    main()
