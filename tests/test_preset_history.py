"""Acceptance tests for PresetChangeHistory (REQ-PH-03..07).

Spec: docs/SPEC_PRESET_HISTORY.md
Runnable without pytest:  python3 -m unittest tests.test_preset_history -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from preset_change_history import PresetChangeHistory


class TestPresetHistory(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self._tmp.name) / "hist.jsonl")
        self.hist = PresetChangeHistory(self.path)

    def tearDown(self):
        self._tmp.cleanup()

    def _seed(self):
        self.hist.record_change("A", "edit", {"v": 0}, {"v": 1}, note="to 1")
        self.hist.record_change("A", "edit", {"v": 1}, {"v": 2}, note="to 2")
        self.hist.record_change("B", "edit", {"x": 0}, {"x": 9}, note="b")

    def test_record_and_count(self):
        self._seed()
        self.assertEqual(self.hist.count(), 3)
        self.assertEqual(self.hist.count("A"), 2)
        self.assertEqual(self.hist.count("B"), 1)

    def test_get_history_filtered(self):
        self._seed()
        a = self.hist.get_history("A")
        self.assertEqual([e["after"] for e in a], [{"v": 1}, {"v": 2}])

    def test_latest_state(self):
        self._seed()
        self.assertEqual(self.hist.latest_state("A"), {"v": 2})
        self.assertIsNone(self.hist.latest_state("missing"))

    def test_get_version_positive_and_negative(self):
        self._seed()
        self.assertEqual(self.hist.get_version("A", 0), {"v": 1})
        self.assertEqual(self.hist.get_version("A", -1), {"v": 2})

    def test_get_version_no_history_raises(self):
        with self.assertRaises(IndexError):
            self.hist.get_version("nope", 0)

    def test_rollback_returns_target_and_records_event(self):
        self._seed()
        target = self.hist.rollback("A", 0)  # roll back to {"v": 1}
        self.assertEqual(target, {"v": 1})
        # a rollback entry was appended
        self.assertEqual(self.hist.count("A"), 3)
        last = self.hist.get_history("A")[-1]
        self.assertEqual(last["change_type"], "rollback")
        self.assertEqual(last["before"], {"v": 2})
        self.assertEqual(last["after"], {"v": 1})
        # latest state now reflects the rollback target
        self.assertEqual(self.hist.latest_state("A"), {"v": 1})

    def test_iter_history_skips_corrupt_lines(self):
        self._seed()
        # append a corrupt line + a valid one
        with open(self.path, "a", encoding="utf-8") as f:
            f.write("{ this is not json\n")
            f.write(json.dumps({
                "timestamp": 0, "preset_name": "A", "change_type": "edit",
                "before": {"v": 2}, "after": {"v": 3}, "user": None, "note": "to 3",
            }) + "\n")
        # iteration must not crash and must include the valid trailing entry
        a = self.hist.get_history("A")
        self.assertEqual(a[-1]["after"], {"v": 3})
        self.assertEqual(self.hist.count("A"), 3)  # 2 seeded + 1 valid appended (corrupt skipped)


if __name__ == "__main__":
    unittest.main(verbosity=2)
