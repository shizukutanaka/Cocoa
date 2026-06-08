"""Acceptance tests for scripts/perf_log_viewer.py.

Spec: docs/SPEC_PERF_LOG_VIEWER.md
Runnable without pytest:  python3 -m unittest tests.test_perf_log_viewer -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from perf_log_viewer import (  # noqa: E402
    collect_snapshots,
    extract_metric,
    format_value,
    iter_log_entries,
    parse_args,
)


class TestExtractMetric(unittest.TestCase):
    def test_simple_path(self):
        self.assertEqual(extract_metric({"a": {"b": 5}}, "a.b"), 5)

    def test_single_key(self):
        self.assertEqual(extract_metric({"cpu": 42}, "cpu"), 42)

    def test_deep_path(self):
        stats = {"memory": {"detail": {"percent": 73.2}}}
        self.assertEqual(extract_metric(stats, "memory.detail.percent"), 73.2)

    def test_missing_leaf_returns_none(self):
        self.assertIsNone(extract_metric({"a": {"b": 5}}, "a.x"))

    def test_missing_root_returns_none(self):
        self.assertIsNone(extract_metric({"a": {"b": 5}}, "z.b"))

    def test_descend_into_scalar_returns_none(self):
        # "a" is an int; trying to descend into "a.b" must yield None, not raise
        self.assertIsNone(extract_metric({"a": 5}, "a.b"))

    def test_empty_stats_returns_none(self):
        self.assertIsNone(extract_metric({}, "a.b"))


class TestFormatValue(unittest.TestCase):
    def test_none_is_dash(self):
        self.assertEqual(format_value(None), "-")

    def test_large_float_is_integer_formatted(self):
        self.assertEqual(format_value(150.0), "150")

    def test_large_value_thousands_separator(self):
        self.assertEqual(format_value(1234.5), "1,234")

    def test_small_float_two_decimals(self):
        self.assertEqual(format_value(12.345), "12.35")

    def test_exactly_100_is_integer(self):
        self.assertEqual(format_value(100), "100")

    def test_just_below_100_two_decimals(self):
        self.assertEqual(format_value(99.9), "99.90")

    def test_string_passthrough(self):
        self.assertEqual(format_value("text"), "text")

    def test_negative_large_value(self):
        self.assertEqual(format_value(-250.7), "-251")

    def test_zero(self):
        self.assertEqual(format_value(0), "0.00")


class TestIterLogEntries(unittest.TestCase):
    def _write(self, td, lines):
        path = Path(td) / "log.jsonl"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def test_parses_valid_lines(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(td, ['{"a": 1}', '{"b": 2}'])
            entries = list(iter_log_entries(path))
            self.assertEqual(entries, [{"a": 1}, {"b": 2}])

    def test_skips_blank_lines(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(td, ['{"a": 1}', "", "   ", '{"b": 2}'])
            entries = list(iter_log_entries(path))
            self.assertEqual(len(entries), 2)

    def test_skips_malformed_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(td, ['{"a": 1}', "{not json", '{"b": 2}'])
            entries = list(iter_log_entries(path))
            self.assertEqual(entries, [{"a": 1}, {"b": 2}])

    def test_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "nope.log"
            with self.assertRaises(FileNotFoundError):
                list(iter_log_entries(missing))


class TestCollectSnapshots(unittest.TestCase):
    def _write(self, td, entries):
        path = Path(td) / "log.jsonl"
        path.write_text(
            "\n".join(json.dumps(e) for e in entries), encoding="utf-8"
        )
        return path

    def test_collects_only_perf_snapshots(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(td, [
                {"message": "performance_snapshot", "timestamp": "t1",
                 "extra": {"stats": {"cpu": {"percent": 10}}}},
                {"message": "something_else", "timestamp": "t2"},
                {"message": "performance_snapshot", "timestamp": "t3",
                 "extra": {"stats": {"cpu": {"percent": 20}}}},
            ])
            snaps = collect_snapshots(path)
            self.assertEqual(len(snaps), 2)
            self.assertEqual(snaps[0]["timestamp"], "t1")
            self.assertEqual(snaps[1]["timestamp"], "t3")

    def test_empty_when_no_snapshots(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(td, [{"message": "info", "timestamp": "t"}])
            self.assertEqual(collect_snapshots(path), [])

    def test_falls_back_to_stats_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(td, [
                {"message": "performance_snapshot",
                 "extra": {"stats": {"timestamp": "inner-ts", "cpu": {"percent": 1}}}},
            ])
            snaps = collect_snapshots(path)
            self.assertEqual(snaps[0]["timestamp"], "inner-ts")

    def test_stats_extracted(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(td, [
                {"message": "performance_snapshot", "timestamp": "t1",
                 "extra": {"stats": {"memory": {"percent": 55.5}}}},
            ])
            snaps = collect_snapshots(path)
            self.assertEqual(
                extract_metric(snaps[0]["stats"], "memory.percent"), 55.5
            )


class TestParseArgs(unittest.TestCase):
    def test_defaults(self):
        args = parse_args([])
        self.assertEqual(args.limit, 20)
        self.assertFalse(args.reverse)

    def test_custom_limit(self):
        args = parse_args(["--limit", "5"])
        self.assertEqual(args.limit, 5)

    def test_reverse_flag(self):
        args = parse_args(["--reverse"])
        self.assertTrue(args.reverse)

    def test_custom_metrics(self):
        args = parse_args(["--metrics", "cpu.percent,memory.percent"])
        self.assertEqual(args.metrics, "cpu.percent,memory.percent")


if __name__ == "__main__":
    unittest.main(verbosity=2)
