"""Tests for main/pagination.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    normalize_pagination,
    paginate,
)


class TestNormalizePagination(unittest.TestCase):
    def test_normal_values_unchanged(self):
        self.assertEqual(normalize_pagination(10, 20), (10, 20))

    def test_negative_offset_clamped_to_zero(self):
        self.assertEqual(normalize_pagination(-5, 20), (0, 20))

    def test_zero_limit_becomes_default(self):
        self.assertEqual(normalize_pagination(0, 0), (0, DEFAULT_LIMIT))

    def test_negative_limit_becomes_default(self):
        self.assertEqual(normalize_pagination(0, -3), (0, DEFAULT_LIMIT))

    def test_huge_limit_capped(self):
        self.assertEqual(normalize_pagination(0, 999999), (0, MAX_LIMIT))

    def test_limit_at_max_unchanged(self):
        self.assertEqual(normalize_pagination(0, MAX_LIMIT), (0, MAX_LIMIT))

    def test_custom_max_limit(self):
        self.assertEqual(normalize_pagination(0, 500, max_limit=200), (0, 200))

    def test_non_numeric_offset_becomes_zero(self):
        self.assertEqual(normalize_pagination("abc", 10), (0, 10))

    def test_non_numeric_limit_becomes_default(self):
        self.assertEqual(normalize_pagination(0, None), (0, DEFAULT_LIMIT))

    def test_numeric_string_coerced(self):
        self.assertEqual(normalize_pagination("5", "10"), (5, 10))


class TestPaginate(unittest.TestCase):
    def setUp(self):
        self.items = list(range(10))  # 0..9

    def test_basic_first_page(self):
        r = paginate(self.items, 0, 3)
        self.assertEqual(r["items"], [0, 1, 2])
        self.assertEqual(r["total"], 10)
        self.assertTrue(r["has_more"])
        self.assertEqual(r["next_offset"], 3)

    def test_last_page_no_more(self):
        r = paginate(self.items, 9, 3)
        self.assertEqual(r["items"], [9])
        self.assertFalse(r["has_more"])
        self.assertIsNone(r["next_offset"])

    def test_offset_past_end(self):
        r = paginate(self.items, 50, 3)
        self.assertEqual(r["items"], [])
        self.assertFalse(r["has_more"])
        self.assertIsNone(r["next_offset"])

    def test_negative_offset_does_not_slice_from_end(self):
        # The whole point: -2 must NOT return items[-2:] (the tail).
        r = paginate(self.items, -2, 3)
        self.assertEqual(r["offset"], 0)
        self.assertEqual(r["items"], [0, 1, 2])

    def test_zero_limit_does_not_loop(self):
        # limit=0 previously yielded empty page + has_more=True + next_offset=0
        # (infinite loop). Now limit is clamped to a positive default.
        r = paginate(self.items, 0, 0)
        self.assertEqual(r["limit"], DEFAULT_LIMIT)
        self.assertNotEqual(r["items"], [])
        # With default >= total here, no further pages.
        self.assertFalse(r["has_more"])
        self.assertIsNone(r["next_offset"])

    def test_huge_limit_capped(self):
        r = paginate(self.items, 0, 999999)
        self.assertEqual(r["limit"], MAX_LIMIT)
        self.assertEqual(r["items"], self.items)  # all 10 fit under the cap

    def test_transform_applied(self):
        r = paginate(self.items, 0, 3, transform=lambda x: x * 10)
        self.assertEqual(r["items"], [0, 10, 20])

    def test_extra_keys_merged(self):
        r = paginate(self.items, 0, 3, query="cats")
        self.assertEqual(r["query"], "cats")
        self.assertIn("total", r)

    def test_contract_keys_present(self):
        r = paginate(self.items, 0, 3)
        for key in ("total", "offset", "limit", "has_more", "next_offset", "items"):
            self.assertIn(key, r)

    def test_empty_input(self):
        r = paginate([], 0, 10)
        self.assertEqual(r["total"], 0)
        self.assertEqual(r["items"], [])
        self.assertFalse(r["has_more"])
        self.assertIsNone(r["next_offset"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
