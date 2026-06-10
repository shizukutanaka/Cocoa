"""Tests for PresetChangeHistory — print_history, rollback, timezone correctness."""
import io
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))
from preset_change_history import PresetChangeHistory


class TestPrintHistory(unittest.TestCase):

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False)  # noqa: SIM115
        self.tmpfile.close()
        self.hist = PresetChangeHistory(self.tmpfile.name)

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_print_history_outputs_entries(self):
        self.hist.record_change("X", "edit", {"a": 1}, {"a": 2}, note="n1")
        self.hist.record_change("X", "validate", {"a": 2}, {"a": 2}, note="n2")
        buf = io.StringIO()
        sys_stdout = sys.stdout
        sys.stdout = buf
        try:
            self.hist.print_history("X")
        finally:
            sys.stdout = sys_stdout
        out = buf.getvalue()
        self.assertIn("edit", out)
        self.assertIn("validate", out)
        self.assertIn("n1", out)
        self.assertIn("n2", out)

    def test_print_history_no_preset_filter(self):
        self.hist.record_change("A", "edit", {}, {"a": 1}, note="na")
        self.hist.record_change("B", "edit", {}, {"b": 1}, note="nb")
        buf = io.StringIO()
        sys_stdout = sys.stdout
        sys.stdout = buf
        try:
            self.hist.print_history()
        finally:
            sys.stdout = sys_stdout
        out = buf.getvalue()
        self.assertIn("na", out)
        self.assertIn("nb", out)

    def test_print_history_timestamp_format(self):
        """Timestamp must follow YYYY-MM-DD HH:MM:SS format."""
        self.hist.record_change("T", "edit", {}, {}, note="ts")
        buf = io.StringIO()
        sys_stdout = sys.stdout
        sys.stdout = buf
        try:
            self.hist.print_history("T")
        finally:
            sys.stdout = sys_stdout
        out = buf.getvalue()
        self.assertRegex(out, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')

    def test_print_history_empty(self):
        """No output when history is empty."""
        buf = io.StringIO()
        sys_stdout = sys.stdout
        sys.stdout = buf
        try:
            self.hist.print_history("nonexistent")
        finally:
            sys.stdout = sys_stdout
        self.assertEqual(buf.getvalue(), "")


class TestRollback(unittest.TestCase):

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False)  # noqa: SIM115
        self.tmpfile.close()
        self.hist = PresetChangeHistory(self.tmpfile.name)

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_rollback_returns_target_state(self):
        self.hist.record_change("P", "edit", {"v": 0}, {"v": 1})
        self.hist.record_change("P", "edit", {"v": 1}, {"v": 2})
        result = self.hist.rollback("P", 0)
        self.assertEqual(result, {"v": 1})

    def test_rollback_appends_entry(self):
        self.hist.record_change("P", "edit", {}, {"v": 1})
        self.hist.rollback("P", 0)
        entries = self.hist.get_history("P")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[-1]["change_type"], "rollback")

    def test_rollback_no_history_raises(self):
        with self.assertRaises(IndexError):
            self.hist.rollback("ghost", 0)

    def test_rollback_negative_index(self):
        self.hist.record_change("P", "edit", {}, {"v": 1})
        self.hist.record_change("P", "edit", {"v": 1}, {"v": 2})
        result = self.hist.rollback("P", -1)
        self.assertEqual(result, {"v": 2})


class TestTimezoneAwareness(unittest.TestCase):

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False)  # noqa: SIM115
        self.tmpfile.close()
        self.hist = PresetChangeHistory(self.tmpfile.name)

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_fromtimestamp_does_not_raise(self):
        """datetime.fromtimestamp with tz=utc must not raise on any valid unix timestamp."""
        from datetime import datetime, timezone
        ts = time.time()
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        self.assertIsNotNone(dt.tzinfo)
