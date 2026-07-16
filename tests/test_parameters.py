"""Smoke tests for parameters.py.

Verifies that the 100 000-parameter table is structurally correct without
loading the full array per assertion (only sample-based checks).
Runnable without pytest:  python3 -m unittest tests.test_parameters -v
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from parameters import AVATAR_PARAMETERS, CATEGORIES, SUBCATEGORIES

EXPECTED_TOTAL = len(CATEGORIES) * len(SUBCATEGORIES) * 1000  # 100 000


class TestParameterTable(unittest.TestCase):
    def test_total_count(self):
        self.assertEqual(len(AVATAR_PARAMETERS), EXPECTED_TOTAL)

    def test_first_entry_has_required_keys(self):
        entry = AVATAR_PARAMETERS[0]
        for key in ("key", "label", "type", "default"):
            self.assertIn(key, entry)

    def test_all_types_are_known(self):
        known = {"slider", "color"}
        types = {e["type"] for e in AVATAR_PARAMETERS}
        self.assertTrue(types.issubset(known), f"Unknown types: {types - known}")

    def test_color_entries_have_hex_default(self):
        color_entries = [e for e in AVATAR_PARAMETERS if e["type"] == "color"]
        self.assertGreater(len(color_entries), 0)
        for e in color_entries[:10]:  # sample check
            self.assertTrue(e["default"].startswith("#"), e)

    def test_slider_entries_have_min_max(self):
        slider_entries = [e for e in AVATAR_PARAMETERS if e["type"] == "slider"]
        self.assertGreater(len(slider_entries), 0)
        for e in slider_entries[:10]:  # sample check
            self.assertIn("min", e)
            self.assertIn("max", e)
            self.assertLessEqual(e["min"], e["default"])
            self.assertLessEqual(e["default"], e["max"])

    def test_color_count(self):
        color_count = sum(1 for e in AVATAR_PARAMETERS if e["type"] == "color")
        self.assertEqual(color_count, len(CATEGORIES) * 1000)

    def test_slider_count(self):
        slider_count = sum(1 for e in AVATAR_PARAMETERS if e["type"] == "slider")
        self.assertEqual(slider_count, len(CATEGORIES) * (len(SUBCATEGORIES) - 1) * 1000)

    def test_keys_are_unique(self):
        keys = [e["key"] for e in AVATAR_PARAMETERS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_key_format(self):
        first = AVATAR_PARAMETERS[0]
        parts = first["key"].split("_")
        self.assertGreaterEqual(len(parts), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
