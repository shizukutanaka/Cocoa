"""Acceptance tests for preset_history_diff_and_rollback pure helpers.

Spec: docs/SPEC_PRESET_HISTORY.md (REQ-PH-08 nested diff, REQ-PH-09 find_entry_by_time)
Runnable without pytest:  python3 -m unittest tests.test_preset_history_diff -v
"""
import sys
import unittest
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

import preset_history_diff_and_rollback as ph


def _ts(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timestamp()


class TestDiffDict(unittest.TestCase):
    def test_flat_changes(self):
        self.assertEqual(ph.diff_dict({"a": 1, "b": 2}, {"a": 1, "b": 3}), ["b: 2 -> 3"])

    def test_added_and_removed_keys(self):
        diffs = ph.diff_dict({"a": 1}, {"b": 2})
        self.assertIn("a: 1 -> None", diffs)
        self.assertIn("b: None -> 2", diffs)

    def test_identical_no_diff(self):
        self.assertEqual(ph.diff_dict({"a": {"x": 1}}, {"a": {"x": 1}}), [])

    def test_nested_dicts_recurse_with_dotted_path(self):
        d1 = {"cfg": {"res": "720p", "fps": 30}}
        d2 = {"cfg": {"res": "1080p", "fps": 30}}
        self.assertEqual(ph.diff_dict(d1, d2), ["cfg.res: 720p -> 1080p"])

    def test_deeply_nested(self):
        d1 = {"a": {"b": {"c": 1}}}
        d2 = {"a": {"b": {"c": 2}}}
        self.assertEqual(ph.diff_dict(d1, d2), ["a.b.c: 1 -> 2"])


class TestFindEntryByTime(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"timestamp": _ts("2024-01-01 10:00:00"), "after": {"v": 1}},
            {"timestamp": _ts("2024-01-01 12:00:00"), "after": {"v": 2}},
            {"timestamp": _ts("2024-01-01 14:00:00"), "after": {"v": 3}},
        ]

    def test_finds_closest(self):
        e = ph.find_entry_by_time(self.entries, "2024-01-01 11:40:00")  # closest to 12:00
        self.assertEqual(e["after"], {"v": 2})

    def test_exact_match(self):
        e = ph.find_entry_by_time(self.entries, "2024-01-01 14:00:00")
        self.assertEqual(e["after"], {"v": 3})

    def test_empty_returns_none(self):
        self.assertIsNone(ph.find_entry_by_time([], "2024-01-01 10:00:00"))

    def test_skips_entries_without_timestamp(self):
        entries = [{"after": {"v": 0}}, {"note": "no ts"}]  # none have numeric timestamp
        self.assertIsNone(ph.find_entry_by_time(entries, "2024-01-01 10:00:00"))

    def test_mixed_valid_and_invalid_timestamps(self):
        entries = [{"note": "bad"}, self.entries[0]]
        e = ph.find_entry_by_time(entries, "2024-01-01 10:00:00")
        self.assertEqual(e["after"], {"v": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
