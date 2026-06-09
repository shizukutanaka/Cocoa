"""Acceptance tests for avatar_parameters, avatar_parameter_sets, joint_range_report.

Spec: docs/SPEC_AVATAR_PARAMETERS.md (REQ-AP-01..05)
Runnable without pytest:  python3 -m unittest tests.test_avatar_parameters -v
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from avatar_parameters import AvatarParameters, estimate_joint_range  # noqa: E402
from avatar_parameter_sets import get_preset, list_presets             # noqa: E402
from joint_range_report import generate_joint_range_report, report_as_records  # noqa: E402


class TestAvatarParametersValidation(unittest.TestCase):
    def _make(self, **kwargs):
        defaults = {"height": 170.0, "weight": 65.0, "muscle_mass": 0.5, "flexibility": 0.5}
        defaults.update(kwargs)
        return AvatarParameters(**defaults)

    def test_valid_construction(self):
        p = self._make()
        self.assertEqual(p.height, 170.0)

    def test_height_zero_raises(self):
        with self.assertRaises(ValueError):
            self._make(height=0)

    def test_height_negative_raises(self):
        with self.assertRaises(ValueError):
            self._make(height=-10)

    def test_weight_zero_raises(self):
        with self.assertRaises(ValueError):
            self._make(weight=0)

    def test_muscle_mass_above_one_raises(self):
        with self.assertRaises(ValueError):
            self._make(muscle_mass=1.1)

    def test_muscle_mass_negative_raises(self):
        with self.assertRaises(ValueError):
            self._make(muscle_mass=-0.1)

    def test_flexibility_above_one_raises(self):
        with self.assertRaises(ValueError):
            self._make(flexibility=1.01)

    def test_boundary_zero_muscle_mass(self):
        p = self._make(muscle_mass=0.0)
        self.assertEqual(p.muscle_mass, 0.0)

    def test_boundary_one_flexibility(self):
        p = self._make(flexibility=1.0)
        self.assertEqual(p.flexibility, 1.0)


class TestEstimateJointRange(unittest.TestCase):
    def _make(self, **kwargs):
        defaults = {"height": 170.0, "weight": 65.0, "muscle_mass": 0.5, "flexibility": 0.5}
        defaults.update(kwargs)
        return AvatarParameters(**defaults)

    def test_known_joint_shoulder(self):
        p = self._make(muscle_mass=0.0, flexibility=0.0)
        deg = estimate_joint_range("shoulder", p)
        self.assertGreaterEqual(deg, 30)
        self.assertLessEqual(deg, 360)

    def test_unknown_joint_uses_default_120(self):
        p = self._make()
        deg = estimate_joint_range("wrist", p)
        self.assertGreaterEqual(deg, 30)
        self.assertLessEqual(deg, 360)

    def test_high_flexibility_increases_range(self):
        low = estimate_joint_range("elbow", self._make(flexibility=0.0, muscle_mass=0.5))
        high = estimate_joint_range("elbow", self._make(flexibility=1.0, muscle_mass=0.5))
        self.assertGreater(high, low)

    def test_high_muscle_decreases_range(self):
        low_muscle = estimate_joint_range("knee", self._make(muscle_mass=0.0, flexibility=0.5))
        high_muscle = estimate_joint_range("knee", self._make(muscle_mass=1.0, flexibility=0.5))
        self.assertGreater(low_muscle, high_muscle)

    def test_result_within_bounds(self):
        for muscle in (0.0, 0.5, 1.0):
            for flex in (0.0, 0.5, 1.0):
                p = self._make(muscle_mass=muscle, flexibility=flex)
                for joint in ("shoulder", "elbow", "knee", "wrist"):
                    deg = estimate_joint_range(joint, p)
                    self.assertGreaterEqual(deg, 30)
                    self.assertLessEqual(deg, 360)


class TestGetPreset(unittest.TestCase):
    def test_known_preset_returns_params(self):
        p = get_preset("標準男性")
        self.assertIsInstance(p, AvatarParameters)
        self.assertGreater(p.height, 0)

    def test_unknown_preset_raises_key_error(self):
        with self.assertRaises(KeyError):
            get_preset("nonexistent_preset_xyz")

    def test_list_presets_nonempty(self):
        names = list_presets()
        self.assertGreater(len(names), 0)
        self.assertIn("標準男性", names)


class TestGenerateJointRangeReport(unittest.TestCase):
    def test_returns_header_and_rows(self):
        header, rows = generate_joint_range_report()
        self.assertIn("体型", header)
        self.assertGreater(len(rows), 0)

    def test_header_contains_joints(self):
        header, _ = generate_joint_range_report(["shoulder", "knee"])
        self.assertIn("shoulder", header)
        self.assertIn("knee", header)

    def test_rows_have_correct_length(self):
        joints = ["shoulder", "elbow"]
        header, rows = generate_joint_range_report(joints)
        expected_len = 1 + len(joints)  # preset_name + one per joint
        for row in rows:
            self.assertEqual(len(row), expected_len)

    def test_values_are_degree_strings(self):
        _, rows = generate_joint_range_report(["shoulder"])
        for row in rows:
            deg_str = row[1]
            deg = float(deg_str)
            self.assertGreaterEqual(deg, 30)
            self.assertLessEqual(deg, 360)


class TestReportAsRecords(unittest.TestCase):
    def test_returns_list_of_dicts(self):
        records = report_as_records()
        self.assertIsInstance(records, list)
        self.assertGreater(len(records), 0)

    def test_each_record_has_preset_key(self):
        for rec in report_as_records():
            self.assertIn("preset", rec)

    def test_each_record_has_joint_keys(self):
        joints = ["shoulder", "elbow", "knee"]
        for rec in report_as_records(joints):
            for j in joints:
                self.assertIn(j, rec)
                self.assertIsInstance(rec[j], float)

    def test_custom_joints(self):
        records = report_as_records(["shoulder"])
        for rec in records:
            self.assertIn("shoulder", rec)
            self.assertNotIn("elbow", rec)

    def test_degree_values_in_range(self):
        for rec in report_as_records():
            for joint in ("shoulder", "elbow", "knee"):
                self.assertGreaterEqual(rec[joint], 30)
                self.assertLessEqual(rec[joint], 360)


if __name__ == "__main__":
    unittest.main(verbosity=2)
