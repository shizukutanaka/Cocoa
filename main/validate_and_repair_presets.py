import os
import glob
import json
import time
import shutil
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Any, Deque, Optional
from performance_monitor import PerformanceMonitor

class PresetPerformanceMonitor:
    """プリセット操作のパフォーマンス監視"""

    def __init__(self):
        self.performance_monitor = PerformanceMonitor({
            "interval": 1.0,
            "history_size": 100,
            "preset_operation_threshold": 1000,  # ms
        })
        self.operation_stats: Dict[str, Any] = {}
        self._op_history: Dict[str, Deque[Dict[str, Any]]] = {}
        self._history_maxlen: int = 100
        self.logger = logging.getLogger(__name__)

    def start_operation(self, operation_name: str) -> str:
        """操作の開始を記録"""
        operation_id = f"{operation_name}_{time.time()}"
        self.operation_stats[operation_id] = {
            "operation": operation_name,
            "start_time": time.time(),
            "status": "running"
        }
        return operation_id

    def end_operation(self, operation_id: str, success: bool = True, metadata: Optional[Dict[str, Any]] = None) -> None:
        """操作の終了を記録"""
        if operation_id not in self.operation_stats:
            return

        stats = self.operation_stats[operation_id]
        end_time = time.time()
        duration = (end_time - stats["start_time"]) * 1000  # ms

        stats.update({
            "end_time": end_time,
            "duration_ms": duration,
            "status": "success" if success else "failed",
            "metadata": metadata or {}
        })

        # パフォーマンス閾値チェック
        threshold = self.performance_monitor.config.get("preset_operation_threshold", 1000)
        if duration > threshold:
            self.logger.warning(
                f"プリセット操作が遅いです: {stats['operation']} ({duration:.2f}ms > {threshold}ms)"
            )

        # 統計収集 (own history — do not mutate PerformanceMonitor internals)
        op_name = stats["operation"]
        if op_name not in self._op_history:
            self._op_history[op_name] = deque(maxlen=self._history_maxlen)
        self._op_history[op_name].append({"timestamp": stats["start_time"], "value": duration})

    def get_performance_report(self) -> Dict[str, Any]:
        """パフォーマンスレポートを取得"""
        op_summary: Dict[str, Any] = {}
        for op_name, history in self._op_history.items():
            values = [s["value"] for s in history]
            if values:
                op_summary[op_name] = {
                    "count": len(values),
                    "avg_ms": sum(values) / len(values),
                    "max_ms": max(values),
                    "min_ms": min(values),
                }
        return {
            "preset_operations": op_summary,
            "recent_operations": list(self.operation_stats.values())[-10:],
            "slow_operations": [
                op for op in self.operation_stats.values()
                if op.get("status") == "success" and op.get("duration_ms", 0) > 500
            ],
        }

def backup_file(filepath, backup_dir):
    os.makedirs(backup_dir, exist_ok=True)
    base = os.path.basename(filepath)
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f"{base}.{ts}.bak")
    shutil.copy2(filepath, backup_path)
    return backup_path

def repair_preset(data):
    # シンプルな自動修復例: 必須キー追加・型修正
    required_keys = {"name": "unknown", "parameters": []}
    for k, v in required_keys.items():
        if k not in data:
            data[k] = v
    if not isinstance(data.get("parameters", []), list):
        data["parameters"] = []
    return data

def validate_and_repair_dir(target_dir, backup_dir="preset_backups", report_path=None):
    """ディレクトリ内の全プリセットJSONを検証し、必要に応じて自動修復する。"""
    monitor = PresetPerformanceMonitor()
    preset_files = glob.glob(os.path.join(target_dir, "*.json"))
    reports = []

    for filepath in preset_files:
        op_id = monitor.start_operation("validate_and_repair")
        entry = {"file": filepath, "repaired": False, "error": None}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            original = json.dumps(data, ensure_ascii=False, sort_keys=True)
            repaired = repair_preset(data)
            if json.dumps(repaired, ensure_ascii=False, sort_keys=True) != original:
                entry["backup"] = backup_file(filepath, backup_dir)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(repaired, f, ensure_ascii=False, indent=2)
                entry["repaired"] = True
            monitor.end_operation(op_id, success=True)
        except (IOError, OSError, json.JSONDecodeError) as e:
            entry["error"] = str(e)
            monitor.end_operation(op_id, success=False)
        reports.append(entry)

    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(reports, f, ensure_ascii=False, indent=2)

    return reports

def main():
    import argparse
    parser = argparse.ArgumentParser(description="プリセット一括バリデーション＆自動修復ツール")
    parser.add_argument("dir", help="プリセットjson格納ディレクトリ")
    parser.add_argument("--backup", default="preset_backups", help="バックアップ保存先")
    parser.add_argument("--report", default=None, help="レポートjson出力パス")
    args = parser.parse_args()
    rep = validate_and_repair_dir(args.dir, args.backup, args.report)
    print(f"{len(rep)}件を検査・修復しました。詳細はレポートまたは標準出力を参照")
    for r in rep:
        print(r)

if __name__ == "__main__":
    main()
