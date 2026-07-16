import argparse
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from preset_change_history import PresetChangeHistory

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    requests = None
    REQUESTS_AVAILABLE = False


def _format_timestamp(ts: Any) -> str:
    """エポック秒を UTC の可読文字列に整形する。解析不能なら str(ts)。"""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError, OSError):
        return str(ts)


def evaluate_entry(entry: Dict[str, Any]) -> Optional[str]:
    """履歴エントリが異常なら Slack 通知メッセージを返す。正常なら None。

    異常条件（純粋関数・I/O なし）:
    - change_type == 'validate' かつ note に 'error' を含む（大小無視）
    - change_type == 'rollback'
    """
    change_type = entry.get('change_type')
    note = entry.get('note') or ''
    ts = _format_timestamp(entry.get('timestamp'))
    name = entry.get('preset_name')

    if change_type == 'validate' and 'error' in note.lower():
        return f"[Cocoa履歴異常] {ts} {name} バリデーションエラー\n{note}"
    if change_type == 'rollback':
        return f"[Cocoa履歴異常] {ts} {name} ロールバック実行\n{note}"
    return None


def send_slack_alert(webhook_url: str, message: str) -> bool:
    """Slack Incoming Webhook へ通知。成功時 True、失敗/未インストール時 False。"""
    if not REQUESTS_AVAILABLE:
        print("requests 未インストールのため Slack 通知をスキップしました")
        return False
    try:
        r = requests.post(webhook_url, json={"text": message}, timeout=5)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"Slack通知失敗: {e}")
        return False


def monitor_history(history_file: str, webhook_url: str, poll_interval: int = 10) -> None:
    """履歴ファイルを追記順（append-only jsonl）に監視し、新規異常を通知する。

    インデックス（処理済み件数）で進捗を管理するため、長時間稼働でも
    メモリ使用量は一定（旧実装は seen セットが無制限に増加していた）。
    """
    print(f"プリセット履歴監視開始: {history_file}")
    hist = PresetChangeHistory(history_file)
    seen_count = 0
    while True:
        try:
            entries = hist.get_history()
            for entry in entries[seen_count:]:
                msg = evaluate_entry(entry)
                if msg:
                    send_slack_alert(webhook_url, msg)
            seen_count = len(entries)
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
