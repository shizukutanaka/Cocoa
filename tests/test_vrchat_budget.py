"""Acceptance tests for the VRChat parameter budget model.

Spec: docs/SPEC_PRESET_PARAMETERS.md (REQ-PM-09/10/11).
Runnable without pytest:  python3 -m unittest tests.test_vrchat_budget -v
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

import vrchat_parameter_budget as vpb


class TestParameterCost(unittest.TestCase):
    def test_type_costs(self):
        self.assertEqual(vpb.parameter_cost({"type": "Bool"}), 1)
        self.assertEqual(vpb.parameter_cost({"type": "Trigger"}), 1)
        self.assertEqual(vpb.parameter_cost({"type": "Int"}), 8)
        self.assertEqual(vpb.parameter_cost({"type": "Float"}), 8)

    def test_case_insensitive(self):
        self.assertEqual(vpb.parameter_cost({"type": "float"}), 8)
        self.assertEqual(vpb.parameter_cost({"type": "BOOL"}), 1)

    def test_unsynced_costs_zero(self):
        self.assertEqual(vpb.parameter_cost({"type": "Float", "synced": False}), 0)

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            vpb.parameter_cost({"type": "Vector3"})
        with self.assertRaises(ValueError):
            vpb.parameter_cost({"type": 123})


class TestAnalyzeBudget(unittest.TestCase):
    def test_exactly_full(self):
        params = [{"name": f"f{i}", "type": "Float"} for i in range(32)]  # 32*8 = 256
        a = vpb.analyze_budget(params)
        self.assertEqual(a["used_bits"], 256)
        self.assertEqual(a["remaining_bits"], 0)
        self.assertFalse(a["over_budget"])
        self.assertEqual(a["synced_count"], 32)
        self.assertEqual(a["breakdown"]["Float"], 32)

    def test_one_bit_over(self):
        params = [{"name": f"f{i}", "type": "Float"} for i in range(32)]
        params.append({"name": "b", "type": "Bool"})  # +1 bit -> 257
        a = vpb.analyze_budget(params)
        self.assertEqual(a["used_bits"], 257)
        self.assertEqual(a["remaining_bits"], -1)
        self.assertTrue(a["over_budget"])

    def test_unsynced_excluded(self):
        params = [
            {"name": "a", "type": "Float"},
            {"name": "b", "type": "Float", "synced": False},
        ]
        a = vpb.analyze_budget(params)
        self.assertEqual(a["used_bits"], 8)
        self.assertEqual(a["synced_count"], 1)

    def test_mixed_breakdown(self):
        params = [
            {"name": "a", "type": "Bool"},
            {"name": "b", "type": "Int"},
            {"name": "c", "type": "Float"},
            {"name": "d", "type": "Trigger"},
        ]
        a = vpb.analyze_budget(params)
        self.assertEqual(a["used_bits"], 1 + 8 + 8 + 1)
        self.assertEqual(a["breakdown"], {"Bool": 1, "Trigger": 1, "Int": 1, "Float": 1})


class TestSuggestions(unittest.TestCase):
    def test_no_suggestions_when_within_budget(self):
        self.assertEqual(vpb.suggest_optimizations([{"name": "a", "type": "Float"}]), [])

    def test_binary_float_downgrade_suggested(self):
        params = [{"name": f"f{i}", "type": "Float"} for i in range(32)]
        params.append({"name": "toggle", "type": "Float", "default": 1})  # binary -> over budget
        suggestions = vpb.suggest_optimizations(params)
        self.assertTrue(any("toggle" in s and "Bool" in s for s in suggestions))
        # always includes the over-budget summary
        self.assertTrue(any("超過" in s for s in suggestions))

    def test_local_named_unsync_suggested(self):
        params = [{"name": f"f{i}", "type": "Float"} for i in range(32)]
        params.append({"name": "local_blink", "type": "Float"})  # over budget + local-named
        suggestions = vpb.suggest_optimizations(params)
        self.assertTrue(any("local_blink" in s and "synced=False" in s for s in suggestions))


class TestCalculateSyncCost(unittest.TestCase):
    def test_empty_list(self):
        self.assertEqual(vpb.calculate_sync_cost([]), 0)

    def test_single_bool(self):
        self.assertEqual(vpb.calculate_sync_cost([{"type": "Bool"}]), 1)

    def test_multiple_params(self):
        params = [{"type": "Bool"}, {"type": "Int"}, {"type": "Float"}]
        self.assertEqual(vpb.calculate_sync_cost(params), 1 + 8 + 8)

    def test_unsynced_excluded(self):
        params = [{"type": "Bool"}, {"type": "Float", "synced": False}]
        self.assertEqual(vpb.calculate_sync_cost(params), 1)

    def test_matches_parameter_cost_sum(self):
        params = [{"type": "Trigger"}, {"type": "Int"}, {"type": "Int"}]
        expected = sum(vpb.parameter_cost(p) for p in params)
        self.assertEqual(vpb.calculate_sync_cost(params), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
