"""Tests for preset_diff_core (pure diff logic).

Runnable without pytest:  python3 -m unittest tests.test_preset_diff -v

Contract (verified against the implementation):
  diff_presets(a, b) -> (equal: bool, diff_lines: list[str])
    * identical presets -> (True, [])
    * differing presets  -> (False, [non-empty lines])
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

import preset_diff_core as pdc  # noqa: E402


class TestDiffPresets(unittest.TestCase):
    def test_identical_presets_report_equal(self):
        a = {"name": "x", "parameters": [1, 2]}
        equal, lines = pdc.diff_presets(a, dict(a))
        self.assertTrue(equal)
        self.assertEqual(lines, [])

    def test_differing_presets_report_not_equal(self):
        a = {"name": "x", "parameters": [1, 2]}
        b = {"name": "y", "parameters": [1, 3]}
        equal, lines = pdc.diff_presets(a, b)
        self.assertFalse(equal)
        self.assertTrue(lines)  # non-empty diff

    def test_sort_keys_does_not_flag_reordering(self):
        a = {"a": 1, "b": 2}
        b = {"b": 2, "a": 1}
        equal, _ = pdc.diff_presets(a, b, sort_keys=True)
        self.assertTrue(equal)


class TestHtmlAndIO(unittest.TestCase):
    def test_generate_html_diff_returns_markup(self):
        html = pdc.generate_html_diff({"name": "a"}, {"name": "b"}, "A", "B")
        self.assertIsInstance(html, str)
        self.assertTrue(any(tag in html.lower() for tag in ("<table", "<pre", "<html", "<div")))

    def test_load_preset_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "preset.json"
            data = {"name": "x", "parameters": [{"k": 1}]}
            path.write_text(json.dumps(data), encoding="utf-8")
            loaded = pdc.load_preset(str(path))
            self.assertEqual(loaded, data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
