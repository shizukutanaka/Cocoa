"""Acceptance tests for joint_range_report.py.

Spec: docs/SPEC_JOINT_RANGE_REPORT.md
Runnable without pytest:  python3 -m unittest tests.test_joint_range_report -v
"""
import io
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from joint_range_report import (
    generate_joint_range_report,
    print_report_table,
    report_as_records,
)


class TestGenerateJointRangeReport(unittest.TestCase):
    def test_returns_tuple(self):
        result = generate_joint_range_report()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_header_starts_with_body_type(self):
        header, _ = generate_joint_range_report()
        self.assertEqual(header[0], "体型")

    def test_default_joints_in_header(self):
        header, _ = generate_joint_range_report()
        for joint in ("shoulder", "elbow", "knee"):
            self.assertIn(joint, header)

    def test_rows_is_list(self):
        _, rows = generate_joint_range_report()
        self.assertIsInstance(rows, list)

    def test_custom_joints(self):
        joints = ["shoulder", "elbow"]
        header, rows = generate_joint_range_report(joint_names=joints)
        self.assertEqual(header, ["体型", "shoulder", "elbow"])

    def test_row_length_matches_header(self):
        header, rows = generate_joint_range_report()
        for row in rows:
            self.assertEqual(len(row), len(header))

    def test_row_degree_cells_are_strings(self):
        header, rows = generate_joint_range_report()
        for row in rows:
            for cell in row[1:]:  # skip preset name
                self.assertIsInstance(cell, str)

    def test_row_degree_format(self):
        """Each degree cell should be a numeric string like '120.0'."""
        header, rows = generate_joint_range_report()
        for row in rows:
            for cell in row[1:]:
                try:
                    float(cell)
                except ValueError:
                    self.fail(f"Non-numeric cell: {cell!r}")

    def test_single_joint(self):
        header, rows = generate_joint_range_report(joint_names=["shoulder"])
        self.assertEqual(len(header), 2)
        for row in rows:
            self.assertEqual(len(row), 2)


class TestReportAsRecords(unittest.TestCase):
    def test_returns_list(self):
        result = report_as_records()
        self.assertIsInstance(result, list)

    def test_each_record_is_dict(self):
        records = report_as_records()
        for rec in records:
            self.assertIsInstance(rec, dict)

    def test_each_record_has_preset_key(self):
        records = report_as_records()
        for rec in records:
            self.assertIn("preset", rec)

    def test_default_joints_in_records(self):
        records = report_as_records()
        for rec in records:
            for joint in ("shoulder", "elbow", "knee"):
                self.assertIn(joint, rec)

    def test_joint_values_are_numeric(self):
        records = report_as_records()
        for rec in records:
            for joint in ("shoulder", "elbow", "knee"):
                self.assertIsInstance(rec[joint], (int, float))

    def test_custom_joints_in_records(self):
        records = report_as_records(joint_names=["shoulder"])
        for rec in records:
            self.assertIn("shoulder", rec)
            self.assertNotIn("elbow", rec)


class TestPrintReportTable(unittest.TestCase):
    def test_empty_rows_does_not_crash(self):
        header = ["体型", "shoulder"]
        print_report_table(header, [])  # should not raise

    def test_with_rows_does_not_crash(self):
        header = ["体型", "shoulder", "elbow"]
        rows = [["slim", "120.0", "110.0"], ["normal", "110.0", "100.0"]]
        print_report_table(header, rows)  # should not raise

    def test_output_contains_header(self):
        import contextlib
        header = ["体型", "shoulder"]
        rows = [["slim", "120.0"]]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print_report_table(header, rows)
        output = buf.getvalue()
        self.assertIn("体型", output)
        self.assertIn("shoulder", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
