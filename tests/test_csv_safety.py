"""Tests for csv_safety.sanitize_csv_cell (CSV formula-injection / CEMI)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "main"))

from csv_safety import sanitize_csv_cell


class TestSanitizeCsvCell(unittest.TestCase):

    def test_escapes_equals_formula(self):
        self.assertEqual(sanitize_csv_cell("=1+1"), "'=1+1")

    def test_escapes_classic_cmd_payload(self):
        self.assertEqual(
            sanitize_csv_cell("=cmd|'/C calc'!A0"),
            "'=cmd|'/C calc'!A0",
        )

    def test_escapes_at_plus_triggers(self):
        self.assertEqual(sanitize_csv_cell("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(sanitize_csv_cell("+1+cmd"), "'+1+cmd")

    def test_escapes_minus_formula_but_not_numbers(self):
        # "-2+cmd" is not a valid float -> treated as a formula -> escaped.
        self.assertEqual(sanitize_csv_cell("-2+cmd"), "'-2+cmd")
        # genuine negative/positive numbers must survive unescaped
        self.assertEqual(sanitize_csv_cell("-5"), "-5")
        self.assertEqual(sanitize_csv_cell("+3.14"), "+3.14")
        self.assertEqual(sanitize_csv_cell("-1.5e3"), "-1.5e3")

    def test_escapes_fullwidth_triggers(self):
        # Excel also evaluates full-width symbols.
        self.assertEqual(sanitize_csv_cell("＝cmd"), "'＝cmd")
        self.assertEqual(sanitize_csv_cell("＠X"), "'＠X")

    def test_escapes_leading_tab_and_cr(self):
        self.assertEqual(sanitize_csv_cell("\t=1"), "'\t=1")
        self.assertEqual(sanitize_csv_cell("\r=1"), "'\r=1")

    def test_plain_text_unchanged(self):
        self.assertEqual(sanitize_csv_cell("hello"), "hello")
        self.assertEqual(sanitize_csv_cell("user@example.com"), "user@example.com")
        self.assertEqual(sanitize_csv_cell("2024-01-01T00:00:00Z"), "2024-01-01T00:00:00Z")

    def test_none_and_empty(self):
        self.assertEqual(sanitize_csv_cell(None), "")
        self.assertEqual(sanitize_csv_cell(""), "")

    def test_non_string_values(self):
        self.assertEqual(sanitize_csv_cell(42), "42")
        self.assertEqual(sanitize_csv_cell(3.5), "3.5")
        self.assertEqual(sanitize_csv_cell(True), "True")

    def test_embedded_at_not_leading_is_safe(self):
        # Trigger only matters at the START of the cell.
        self.assertEqual(sanitize_csv_cell("a=b"), "a=b")
        self.assertEqual(sanitize_csv_cell("name (=label)"), "name (=label)")


if __name__ == "__main__":
    unittest.main()
