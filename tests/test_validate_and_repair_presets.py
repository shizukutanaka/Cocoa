"""Acceptance tests for validate_and_repair_presets.py.

Spec: docs/SPEC_VALIDATE_AND_REPAIR_PRESETS.md (REQ-VRP-01..04)
Runnable without pytest:  python3 -m unittest tests.test_validate_and_repair_presets -v
"""
import json
import sys
import tempfile
import unittest
from collections import deque
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from validate_and_repair_presets import (  # noqa: E402
    PresetPerformanceMonitor,
    backup_file,
    repair_preset,
    validate_and_repair_dir,
)


class TestRepairPreset(unittest.TestCase):
    def test_adds_missing_name(self):
        data = {"parameters": []}
        result = repair_preset(data)
        self.assertIn("name", result)
        self.assertEqual(result["name"], "unknown")

    def test_adds_missing_parameters(self):
        data = {"name": "foo"}
        result = repair_preset(data)
        self.assertIn("parameters", result)
        self.assertEqual(result["parameters"], [])

    def test_does_not_overwrite_existing_name(self):
        data = {"name": "my_preset", "parameters": []}
        result = repair_preset(data)
        self.assertEqual(result["name"], "my_preset")

    def test_fixes_non_list_parameters(self):
        data = {"name": "x", "parameters": "bad"}
        result = repair_preset(data)
        self.assertIsInstance(result["parameters"], list)

    def test_valid_preset_unchanged(self):
        data = {"name": "ok", "parameters": [{"name": "a", "value": 1}]}
        original = json.dumps(data, sort_keys=True)
        result = repair_preset(data)
        self.assertEqual(json.dumps(result, sort_keys=True), original)


class TestBackupFile(unittest.TestCase):
    def test_backup_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "preset.json"
            src.write_text('{"name": "x"}', encoding="utf-8")
            backup_dir = Path(td) / "backups"
            backup_path = backup_file(str(src), str(backup_dir))
            self.assertTrue(Path(backup_path).exists())

    def test_backup_creates_backup_dir(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "preset.json"
            src.write_text("{}", encoding="utf-8")
            backup_dir = Path(td) / "new_backups"
            backup_file(str(src), str(backup_dir))
            self.assertTrue(backup_dir.exists())

    def test_backup_filename_contains_original(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "my_preset.json"
            src.write_text("{}", encoding="utf-8")
            backup_dir = Path(td) / "bak"
            backup_path = backup_file(str(src), str(backup_dir))
            self.assertIn("my_preset.json", Path(backup_path).name)

    def test_backup_filename_contains_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "x.json"
            src.write_text("{}", encoding="utf-8")
            backup_dir = Path(td) / "bak"
            backup_path = backup_file(str(src), str(backup_dir))
            # Timestamp portion: YYYYMMDD_HHMMSS — 15 chars
            name = Path(backup_path).name
            self.assertRegex(name, r"\d{8}_\d{6}")


class TestValidateAndRepairDir(unittest.TestCase):
    def test_empty_dir_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as td:
            result = validate_and_repair_dir(td)
            self.assertEqual(result, [])

    def test_valid_preset_not_repaired(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "ok.json"
            p.write_text('{"name": "good", "parameters": []}', encoding="utf-8")
            result = validate_and_repair_dir(td, backup_dir=str(Path(td) / "bak"))
            self.assertEqual(len(result), 1)
            self.assertFalse(result[0]["repaired"])
            self.assertIsNone(result[0]["error"])

    def test_preset_missing_name_repaired(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.json"
            p.write_text('{"parameters": []}', encoding="utf-8")
            result = validate_and_repair_dir(td, backup_dir=str(Path(td) / "bak"))
            self.assertEqual(len(result), 1)
            self.assertTrue(result[0]["repaired"])

    def test_repaired_file_is_readable_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.json"
            p.write_text('{"parameters": []}', encoding="utf-8")
            validate_and_repair_dir(td, backup_dir=str(Path(td) / "bak"))
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("name", data)

    def test_broken_json_recorded_as_error(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "broken.json"
            p.write_text("{not valid json", encoding="utf-8")
            result = validate_and_repair_dir(td, backup_dir=str(Path(td) / "bak"))
            self.assertEqual(len(result), 1)
            self.assertIsNotNone(result[0]["error"])
            self.assertFalse(result[0]["repaired"])

    def test_report_path_writes_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "p.json"
            p.write_text('{"name": "a", "parameters": []}', encoding="utf-8")
            report_path = str(Path(td) / "report.json")
            validate_and_repair_dir(td, backup_dir=str(Path(td) / "bak"), report_path=report_path)
            with open(report_path, encoding="utf-8") as f:
                report = json.load(f)
            self.assertIsInstance(report, list)


class TestPresetPerformanceMonitor(unittest.TestCase):
    def test_constructor_does_not_raise(self):
        pm = PresetPerformanceMonitor()
        self.assertIsNotNone(pm)

    def test_start_operation_returns_string(self):
        pm = PresetPerformanceMonitor()
        op_id = pm.start_operation("test_op")
        self.assertIsInstance(op_id, str)

    def test_end_operation_records_stats(self):
        pm = PresetPerformanceMonitor()
        op_id = pm.start_operation("my_op")
        pm.end_operation(op_id, success=True)
        self.assertIn(op_id, pm.operation_stats)
        self.assertEqual(pm.operation_stats[op_id]["status"], "success")

    def test_end_operation_failure_status(self):
        pm = PresetPerformanceMonitor()
        op_id = pm.start_operation("my_op")
        pm.end_operation(op_id, success=False)
        self.assertEqual(pm.operation_stats[op_id]["status"], "failed")

    def test_end_operation_stores_duration(self):
        pm = PresetPerformanceMonitor()
        op_id = pm.start_operation("my_op")
        pm.end_operation(op_id)
        self.assertIn("duration_ms", pm.operation_stats[op_id])
        self.assertGreaterEqual(pm.operation_stats[op_id]["duration_ms"], 0)

    def test_end_operation_unknown_id_does_not_raise(self):
        pm = PresetPerformanceMonitor()
        pm.end_operation("nonexistent_id")  # should silently return

    def test_op_history_uses_deque(self):
        pm = PresetPerformanceMonitor()
        op_id = pm.start_operation("check")
        pm.end_operation(op_id)
        self.assertIn("check", pm._op_history)
        self.assertIsInstance(pm._op_history["check"], deque)

    def test_op_history_bounded(self):
        pm = PresetPerformanceMonitor()
        pm._history_maxlen = 5
        for _ in range(10):
            op_id = pm.start_operation("loop_op")
            pm.end_operation(op_id)
            # Re-create deque with new maxlen for subsequent ops
        # The deque maxlen is set on first creation; check at most maxlen items
        history = pm._op_history.get("loop_op", deque())
        self.assertLessEqual(len(history), pm._history_maxlen)

    def test_performance_monitor_metrics_history_not_mutated(self):
        pm = PresetPerformanceMonitor()
        original_keys = set(pm.performance_monitor.metrics_history.keys())
        op_id = pm.start_operation("custom_metric")
        pm.end_operation(op_id)
        after_keys = set(pm.performance_monitor.metrics_history.keys())
        self.assertEqual(original_keys, after_keys)

    def test_get_performance_report_has_required_keys(self):
        pm = PresetPerformanceMonitor()
        report = pm.get_performance_report()
        for key in ("preset_operations", "recent_operations", "slow_operations"):
            self.assertIn(key, report)

    def test_get_performance_report_after_operations(self):
        pm = PresetPerformanceMonitor()
        op_id = pm.start_operation("validate_and_repair")
        pm.end_operation(op_id, success=True)
        report = pm.get_performance_report()
        self.assertIn("validate_and_repair", report["preset_operations"])

    def test_preset_operations_summary_has_stats(self):
        pm = PresetPerformanceMonitor()
        op_id = pm.start_operation("op")
        pm.end_operation(op_id)
        report = pm.get_performance_report()
        summary = report["preset_operations"].get("op", {})
        for field in ("count", "avg_ms", "max_ms", "min_ms"):
            self.assertIn(field, summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
