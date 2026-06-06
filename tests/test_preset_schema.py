"""Acceptance tests for preset_schema (REQ-PM-07 / REQ-PM-12).

Spec: docs/SPEC_PRESET_PARAMETERS.md
Runnable without pytest:  python3 -m unittest tests.test_preset_schema -v
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

import preset_schema as ps  # noqa: E402


def _params(n_float):
    return [{"name": f"f{i}", "type": "Float"} for i in range(n_float)]


class TestValidatePresetSchema(unittest.TestCase):
    def test_minimal_valid(self):
        r = ps.validate_preset_schema({"name": "ok", "parameters": []})
        self.assertTrue(r["valid"], r["errors"])
        self.assertEqual(r["errors"], [])

    def test_valid_with_parameters(self):
        preset = {"name": "p", "parameters": [
            {"name": "Smile", "type": "Float", "synced": True, "default": 0},
            {"name": "Toggle", "type": "Bool", "default": True},
        ]}
        self.assertTrue(ps.validate_preset_schema(preset)["valid"])

    def test_non_object_rejected(self):
        self.assertFalse(ps.validate_preset_schema(["not", "a", "dict"])["valid"])

    def test_missing_name(self):
        r = ps.validate_preset_schema({"parameters": []})
        self.assertFalse(r["valid"])
        self.assertTrue(any("name" in e for e in r["errors"]))

    def test_parameters_not_list(self):
        r = ps.validate_preset_schema({"name": "x", "parameters": "nope"})
        self.assertFalse(r["valid"])
        self.assertTrue(any("parameters" in e for e in r["errors"]))

    def test_bad_parameter_type(self):
        r = ps.validate_preset_schema({"name": "x", "parameters": [{"name": "a", "type": "Vector3"}]})
        self.assertFalse(r["valid"])

    def test_duplicate_parameter_names(self):
        r = ps.validate_preset_schema({"name": "x", "parameters": [
            {"name": "dup", "type": "Bool"},
            {"name": "dup", "type": "Int"},
        ]})
        self.assertFalse(r["valid"])
        self.assertTrue(any("duplicate" in e for e in r["errors"]))

    def test_bad_synced_type(self):
        r = ps.validate_preset_schema({"name": "x", "parameters": [
            {"name": "a", "type": "Bool", "synced": "yes"},
        ]})
        self.assertFalse(r["valid"])

    def test_default_type_mismatch_is_warning_not_error(self):
        r = ps.validate_preset_schema({"name": "x", "parameters": [
            {"name": "a", "type": "Bool", "default": 5},
        ]})
        self.assertTrue(r["valid"])  # mismatch is a warning, not a hard error
        self.assertTrue(r["warnings"])


class TestAnalyzePreset(unittest.TestCase):
    def test_invalid_schema_skips_budget(self):
        r = ps.analyze_preset({"parameters": "bad"})
        self.assertFalse(r["schema"]["valid"])
        self.assertIsNone(r["budget"])
        self.assertEqual(r["suggestions"], [])

    def test_valid_within_budget(self):
        r = ps.analyze_preset({"name": "p", "parameters": _params(10)})  # 80 bits
        self.assertTrue(r["schema"]["valid"])
        self.assertEqual(r["budget"]["used_bits"], 80)
        self.assertFalse(r["budget"]["over_budget"])
        self.assertEqual(r["suggestions"], [])

    def test_valid_over_budget_has_suggestions(self):
        params = _params(32) + [{"name": "extra", "type": "Float", "default": 1}]  # 33*8=264
        r = ps.analyze_preset({"name": "p", "parameters": params})
        self.assertTrue(r["schema"]["valid"])
        self.assertTrue(r["budget"]["over_budget"])
        self.assertTrue(r["suggestions"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
