"""Acceptance tests for preset_history_alert.py.

Spec: docs/PRODUCT_CATEGORY_MAP.md (category 2, preset_history_alert)
Runnable without pytest:  python3 -m unittest tests.test_preset_history_alert -v

The pure anomaly-detection logic (evaluate_entry) was extracted from the
I/O-bound monitor loop specifically to make it testable.
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from preset_history_alert import (
    _format_timestamp,
    evaluate_entry,
    send_slack_alert,
)


class TestEvaluateEntry(unittest.TestCase):
    def _entry(self, **kw):
        base = {"change_type": "edit", "note": "", "preset_name": "A", "timestamp": 1700000000}
        base.update(kw)
        return base

    def test_validate_error_triggers_alert(self):
        msg = evaluate_entry(self._entry(change_type="validate", note="Validation ERROR: bad value"))
        self.assertIsNotNone(msg)
        self.assertIn("バリデーションエラー", msg)

    def test_validate_error_case_insensitive(self):
        msg = evaluate_entry(self._entry(change_type="validate", note="some error here"))
        self.assertIsNotNone(msg)

    def test_validate_without_error_no_alert(self):
        msg = evaluate_entry(self._entry(change_type="validate", note="OK passed"))
        self.assertIsNone(msg)

    def test_validate_none_note_no_alert(self):
        msg = evaluate_entry(self._entry(change_type="validate", note=None))
        self.assertIsNone(msg)

    def test_rollback_triggers_alert(self):
        msg = evaluate_entry(self._entry(change_type="rollback", note="rollback to #2"))
        self.assertIsNotNone(msg)
        self.assertIn("ロールバック", msg)

    def test_edit_no_alert(self):
        self.assertIsNone(evaluate_entry(self._entry(change_type="edit")))

    def test_apply_no_alert(self):
        self.assertIsNone(evaluate_entry(self._entry(change_type="apply")))

    def test_message_contains_preset_name(self):
        msg = evaluate_entry(self._entry(change_type="rollback", preset_name="MyAvatar"))
        self.assertIn("MyAvatar", msg)

    def test_missing_change_type_no_crash(self):
        # entry without change_type should not raise, returns None
        self.assertIsNone(evaluate_entry({"preset_name": "A", "timestamp": 1700000000}))

    def test_missing_fields_no_crash(self):
        # completely empty entry
        self.assertIsNone(evaluate_entry({}))


class TestFormatTimestamp(unittest.TestCase):
    def test_epoch_to_utc_string(self):
        # 1700000000 = 2023-11-14 22:13:20 UTC
        self.assertEqual(_format_timestamp(1700000000), "2023-11-14 22:13:20")

    def test_float_timestamp(self):
        result = _format_timestamp(1700000000.5)
        self.assertEqual(result, "2023-11-14 22:13:20")

    def test_invalid_timestamp_falls_back_to_str(self):
        self.assertEqual(_format_timestamp("not-a-number"), "not-a-number")

    def test_none_timestamp_falls_back(self):
        self.assertEqual(_format_timestamp(None), "None")


class TestSendSlackAlert(unittest.TestCase):
    def test_returns_bool(self):
        # In an environment without requests, or with a bad URL, returns False
        # without raising. We pass an obviously invalid URL; the function must
        # catch any error and return a boolean.
        result = send_slack_alert("http://127.0.0.1:0/invalid", "test message")
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main(verbosity=2)
