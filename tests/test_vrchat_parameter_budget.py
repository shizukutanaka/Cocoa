"""Tests for main/vrchat_parameter_budget.py."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "main"))

import vrchat_parameter_budget as vpb


class TestNormalizeType(unittest.TestCase):
    def test_canonical_lowercase(self):
        for t in ("bool", "trigger", "int", "float"):
            self.assertEqual(vpb._normalize_type(t), t)

    def test_case_insensitive(self):
        self.assertEqual(vpb._normalize_type("Bool"), "bool")
        self.assertEqual(vpb._normalize_type("FLOAT"), "float")
        self.assertEqual(vpb._normalize_type("Trigger"), "trigger")

    def test_whitespace_stripped(self):
        self.assertEqual(vpb._normalize_type("  Int  "), "int")

    def test_unknown_raises(self):
        with self.assertRaises(ValueError):
            vpb._normalize_type("String")

    def test_non_string_raises(self):
        with self.assertRaises(ValueError):
            vpb._normalize_type(42)


class TestParameterCost(unittest.TestCase):
    def test_bool_cost(self):
        self.assertEqual(vpb.parameter_cost({"type": "Bool", "synced": True}), 1)

    def test_trigger_cost(self):
        self.assertEqual(vpb.parameter_cost({"type": "Trigger", "synced": True}), 1)

    def test_int_cost(self):
        self.assertEqual(vpb.parameter_cost({"type": "Int", "synced": True}), 8)

    def test_float_cost(self):
        self.assertEqual(vpb.parameter_cost({"type": "Float", "synced": True}), 8)

    def test_unsynced_is_zero(self):
        self.assertEqual(vpb.parameter_cost({"type": "Float", "synced": False}), 0)

    def test_synced_default_is_true(self):
        self.assertEqual(vpb.parameter_cost({"type": "Bool"}), 1)


class TestCalculateSyncCost(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(vpb.calculate_sync_cost([]), 0)

    def test_mixed_types(self):
        params = [
            {"type": "Bool"},
            {"type": "Int"},
            {"type": "Float", "synced": False},
        ]
        self.assertEqual(vpb.calculate_sync_cost(params), 1 + 8)

    def test_all_unsynced(self):
        params = [{"type": "Int", "synced": False}, {"type": "Float", "synced": False}]
        self.assertEqual(vpb.calculate_sync_cost(params), 0)


class TestAnalyzeBudget(unittest.TestCase):
    def test_basic_structure(self):
        result = vpb.analyze_budget([{"type": "Bool"}, {"type": "Int"}])
        self.assertIn("budget_bits", result)
        self.assertIn("used_bits", result)
        self.assertIn("remaining_bits", result)
        self.assertIn("over_budget", result)
        self.assertIn("synced_count", result)

    def test_under_budget(self):
        params = [{"type": "Bool"}] * 10
        result = vpb.analyze_budget(params)
        self.assertFalse(result["over_budget"])
        self.assertEqual(result["used_bits"], 10)
        self.assertEqual(result["remaining_bits"], 246)

    def test_over_budget(self):
        params = [{"type": "Float"}] * 33  # 33 * 8 = 264 > 256
        result = vpb.analyze_budget(params)
        self.assertTrue(result["over_budget"])

    def test_unsynced_not_counted(self):
        params = [{"type": "Int", "synced": False}] * 100
        result = vpb.analyze_budget(params)
        self.assertEqual(result["used_bits"], 0)
        self.assertEqual(result["synced_count"], 0)

    def test_breakdown_counts(self):
        params = [{"type": "Bool"}, {"type": "Bool"}, {"type": "Int"}]
        result = vpb.analyze_budget(params)
        self.assertEqual(result["breakdown"]["Bool"], 2)
        self.assertEqual(result["breakdown"]["Int"], 1)


class TestSuggestOptimizations(unittest.TestCase):
    def test_no_suggestions_under_budget(self):
        params = [{"type": "Bool"}]
        self.assertEqual(vpb.suggest_optimizations(params), [])

    def test_suggestions_over_budget(self):
        params = [{"type": "Float"}] * 33
        suggestions = vpb.suggest_optimizations(params)
        self.assertGreater(len(suggestions), 0)
        self.assertTrue(any("超過" in s for s in suggestions))

    def test_binary_float_suggestion(self):
        params = [{"type": "Float"}] * 33
        params[0]["default"] = 0
        params[0]["name"] = "test_param"
        suggestions = vpb.suggest_optimizations(params)
        self.assertTrue(any("Bool" in s for s in suggestions))

    def test_local_param_suggestion(self):
        params = [{"type": "Int"}] * 33
        params[0]["name"] = "local_speed"
        suggestions = vpb.suggest_optimizations(params)
        self.assertTrue(any("local_speed" in s for s in suggestions))


class TestLooksBinary(unittest.TestCase):
    def test_bool_true(self):
        self.assertTrue(vpb._looks_binary(True))
        self.assertTrue(vpb._looks_binary(False))

    def test_zero_one(self):
        self.assertTrue(vpb._looks_binary(0))
        self.assertTrue(vpb._looks_binary(1))
        self.assertTrue(vpb._looks_binary(0.0))
        self.assertTrue(vpb._looks_binary(1.0))

    def test_other_values(self):
        self.assertFalse(vpb._looks_binary(2))
        self.assertFalse(vpb._looks_binary(0.5))
        self.assertFalse(vpb._looks_binary("0"))


if __name__ == "__main__":
    unittest.main()
