"""Tests for main/preset_history_diff_and_rollback.py."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "main"))

from preset_history_diff_and_rollback import diff_dict, find_entry_by_time


class TestDiffDict(unittest.TestCase):

    def test_identical_dicts_return_empty(self):
        self.assertEqual(diff_dict({"a": 1}, {"a": 1}), [])

    def test_single_changed_value(self):
        diffs = diff_dict({"x": 1}, {"x": 2})
        self.assertEqual(len(diffs), 1)
        self.assertIn("x", diffs[0])
        self.assertIn("1", diffs[0])
        self.assertIn("2", diffs[0])

    def test_added_key_detected(self):
        diffs = diff_dict({}, {"new_key": 42})
        self.assertEqual(len(diffs), 1)
        self.assertIn("new_key", diffs[0])

    def test_removed_key_detected(self):
        diffs = diff_dict({"old_key": 7}, {})
        self.assertEqual(len(diffs), 1)
        self.assertIn("old_key", diffs[0])

    def test_multiple_changes(self):
        diffs = diff_dict({"a": 1, "b": 2}, {"a": 10, "b": 20})
        self.assertEqual(len(diffs), 2)

    def test_nested_dict_diff(self):
        d1 = {"settings": {"volume": 50, "mute": False}}
        d2 = {"settings": {"volume": 80, "mute": False}}
        diffs = diff_dict(d1, d2)
        self.assertEqual(len(diffs), 1)
        self.assertIn("settings.volume", diffs[0])

    def test_deeply_nested_diff(self):
        d1 = {"a": {"b": {"c": 1}}}
        d2 = {"a": {"b": {"c": 2}}}
        diffs = diff_dict(d1, d2)
        self.assertEqual(len(diffs), 1)
        self.assertIn("a.b.c", diffs[0])

    def test_nested_dict_added(self):
        d1 = {"a": {}}
        d2 = {"a": {"x": 1}}
        diffs = diff_dict(d1, d2)
        self.assertEqual(len(diffs), 1)
        self.assertIn("a.x", diffs[0])

    def test_prefix_applied(self):
        diffs = diff_dict({"k": 1}, {"k": 2}, prefix="root.")
        self.assertEqual(len(diffs), 1)
        self.assertTrue(diffs[0].startswith("root.k"))

    def test_empty_dicts(self):
        self.assertEqual(diff_dict({}, {}), [])

    def test_type_change_detected(self):
        diffs = diff_dict({"v": 1}, {"v": "one"})
        self.assertEqual(len(diffs), 1)
        self.assertIn("v", diffs[0])

    def test_keys_sorted_in_output(self):
        diffs = diff_dict({"z": 1, "a": 2}, {"z": 9, "a": 8})
        # 'a' should come before 'z' since keys are sorted
        self.assertLess(diffs.index(next(d for d in diffs if "a:" in d)),
                        diffs.index(next(d for d in diffs if "z:" in d)))

    def test_none_value_diff(self):
        diffs = diff_dict({"x": None}, {"x": 0})
        self.assertEqual(len(diffs), 1)

    def test_bool_value_diff(self):
        diffs = diff_dict({"flag": True}, {"flag": False})
        self.assertEqual(len(diffs), 1)


class TestFindEntryByTime(unittest.TestCase):

    def _make_entry(self, ts_unix, data):
        return {"timestamp": ts_unix, "after": data}

    def test_returns_none_for_empty_list(self):
        self.assertIsNone(find_entry_by_time([], "2024-01-01 00:00:00"))

    def test_exact_match(self):
        from datetime import datetime
        ts_str = "2024-06-15 12:00:00"
        unix_ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
        entries = [self._make_entry(unix_ts, {"v": 1})]
        result = find_entry_by_time(entries, ts_str)
        self.assertIsNotNone(result)
        self.assertEqual(result["after"]["v"], 1)

    def test_closest_entry_returned(self):
        from datetime import datetime
        base = datetime.strptime("2024-01-01 12:00:00", "%Y-%m-%d %H:%M:%S").timestamp()
        entries = [
            self._make_entry(base - 3600, {"label": "early"}),
            self._make_entry(base + 60, {"label": "close"}),
            self._make_entry(base + 7200, {"label": "late"}),
        ]
        result = find_entry_by_time(entries, "2024-01-01 12:00:00")
        self.assertEqual(result["after"]["label"], "close")

    def test_entries_without_timestamp_skipped(self):
        from datetime import datetime
        ts_str = "2024-01-01 00:00:00"
        unix_ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
        entries = [
            {"after": {"label": "no_ts"}},          # no timestamp key
            {"timestamp": "not_a_number", "after": {"label": "bad_ts"}},
            self._make_entry(unix_ts, {"label": "good"}),
        ]
        result = find_entry_by_time(entries, ts_str)
        self.assertEqual(result["after"]["label"], "good")

    def test_all_entries_missing_timestamp_returns_none(self):
        entries = [{"after": {"x": 1}}, {"after": {"x": 2}}]
        self.assertIsNone(find_entry_by_time(entries, "2024-01-01 00:00:00"))

    def test_single_entry_always_returned(self):
        entries = [self._make_entry(0.0, {"v": "only"})]
        result = find_entry_by_time(entries, "2024-06-01 10:00:00")
        self.assertEqual(result["after"]["v"], "only")

    def test_float_timestamp_accepted(self):
        from datetime import datetime
        ts_str = "2024-03-15 08:30:00"
        unix_ts = float(datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp())
        entries = [self._make_entry(unix_ts, {"data": "float_ts"})]
        result = find_entry_by_time(entries, ts_str)
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
