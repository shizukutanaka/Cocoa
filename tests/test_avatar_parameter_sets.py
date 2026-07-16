"""Acceptance tests for avatar_parameter_sets.py.

Spec: PRESET_SETS must expose all 4 built-in presets via list_presets() /
get_preset(); unknown names raise KeyError; parameter values are in-range.
Runnable without pytest:  python3 -m unittest tests.test_avatar_parameter_sets -v
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from avatar_parameter_sets import get_preset, list_presets
from avatar_parameters import AvatarParameters

EXPECTED_PRESET_COUNT = 4


class TestListPresets(unittest.TestCase):
    def test_returns_list(self):
        self.assertIsInstance(list_presets(), list)

    def test_returns_all_four_presets(self):
        self.assertEqual(len(list_presets()), EXPECTED_PRESET_COUNT)

    def test_all_items_are_strings(self):
        for name in list_presets():
            self.assertIsInstance(name, str)

    def test_expected_names_present(self):
        names = list_presets()
        for expected in ("標準男性", "標準女性", "筋肉質", "柔軟体型"):
            self.assertIn(expected, names)


class TestGetPreset(unittest.TestCase):
    def test_returns_avatar_parameters_instance(self):
        preset = get_preset("標準男性")
        self.assertIsInstance(preset, AvatarParameters)

    def test_standard_male_values(self):
        p = get_preset("標準男性")
        self.assertAlmostEqual(p.height, 172.0)
        self.assertAlmostEqual(p.weight, 68.0)

    def test_standard_female_values(self):
        p = get_preset("標準女性")
        self.assertAlmostEqual(p.height, 158.0)
        self.assertAlmostEqual(p.weight, 54.0)

    def test_unknown_name_raises_key_error(self):
        with self.assertRaises(KeyError):
            get_preset("存在しないプリセット")

    def test_all_presets_retrievable(self):
        for name in list_presets():
            with self.subTest(name=name):
                self.assertIsInstance(get_preset(name), AvatarParameters)


class TestPresetValueRanges(unittest.TestCase):
    def test_height_positive(self):
        for name in list_presets():
            with self.subTest(name=name):
                self.assertGreater(get_preset(name).height, 0)

    def test_weight_positive(self):
        for name in list_presets():
            with self.subTest(name=name):
                self.assertGreater(get_preset(name).weight, 0)

    def test_muscle_mass_in_unit_range(self):
        for name in list_presets():
            with self.subTest(name=name):
                v = get_preset(name).muscle_mass
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 1.0)

    def test_flexibility_in_unit_range(self):
        for name in list_presets():
            with self.subTest(name=name):
                v = get_preset(name).flexibility
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 1.0)

    def test_bone_lengths_have_arm_and_leg(self):
        for name in list_presets():
            with self.subTest(name=name):
                bl = get_preset(name).bone_lengths
                self.assertIn("arm", bl)
                self.assertIn("leg", bl)

    def test_bone_lengths_positive(self):
        for name in list_presets():
            with self.subTest(name=name):
                bl = get_preset(name).bone_lengths
                self.assertGreater(bl["arm"], 0)
                self.assertGreater(bl["leg"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
