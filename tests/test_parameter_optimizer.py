"""Tests for main/parameter_optimizer.py."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "main"))

from parameter_optimizer import NUMPY_AVAILABLE, SCIPY_AVAILABLE, ParameterOptimizer

_FULL_DEPS = NUMPY_AVAILABLE and SCIPY_AVAILABLE


def _make_params(*values, include_bounds=False):
    """Build a list of parameter dicts with given values."""
    params = []
    for i, v in enumerate(values):
        p = {"name": f"param_{i}", "value": v}
        if include_bounds:
            p["min"] = -50.0
            p["max"] = 50.0
        params.append(p)
    return params


class TestCalculateBounds(unittest.TestCase):

    def test_default_bounds_used_when_missing(self):
        params = _make_params(1.0, 2.0)
        opt = ParameterOptimizer(params)
        self.assertEqual(opt.bounds, [(-100, 100), (-100, 100)])

    def test_explicit_bounds_respected(self):
        params = _make_params(0.0, 0.5, include_bounds=True)
        opt = ParameterOptimizer(params)
        self.assertEqual(opt.bounds, [(-50.0, 50.0), (-50.0, 50.0)])

    def test_mixed_bounds(self):
        params = [
            {"name": "a", "value": 1.0, "min": 0.0, "max": 10.0},
            {"name": "b", "value": 2.0},
        ]
        opt = ParameterOptimizer(params)
        self.assertEqual(opt.bounds[0], (0.0, 10.0))
        self.assertEqual(opt.bounds[1], (-100, 100))

    def test_empty_params_gives_empty_bounds(self):
        opt = ParameterOptimizer([])
        self.assertEqual(opt.bounds, [])

    def test_single_param_bounds(self):
        opt = ParameterOptimizer([{"name": "x", "value": 5.0, "min": 1.0, "max": 9.0}])
        self.assertEqual(len(opt.bounds), 1)
        self.assertEqual(opt.bounds[0], (1.0, 9.0))

    def test_bounds_length_matches_params(self):
        params = _make_params(1, 2, 3, 4, 5)
        opt = ParameterOptimizer(params)
        self.assertEqual(len(opt.bounds), 5)


class TestOptimize(unittest.TestCase):

    @unittest.skipUnless(_FULL_DEPS, "numpy/scipy not installed")
    def test_optimize_returns_success_dict(self):
        params = _make_params(1.0, 2.0, 3.0)
        opt = ParameterOptimizer(params)
        result = opt.optimize()
        self.assertTrue(result["success"])
        self.assertIn("optimized_parameters", result)
        self.assertIn("message", result)
        self.assertIn("performance_gain", result)

    @unittest.skipUnless(_FULL_DEPS, "numpy/scipy not installed")
    def test_optimized_params_count_matches_input(self):
        params = _make_params(5.0, 10.0, 15.0)
        opt = ParameterOptimizer(params)
        result = opt.optimize()
        self.assertEqual(len(result["optimized_parameters"]), 3)

    @unittest.skipUnless(_FULL_DEPS, "numpy/scipy not installed")
    def test_performance_gain_is_float(self):
        params = _make_params(1.0, 100.0)
        opt = ParameterOptimizer(params)
        result = opt.optimize()
        self.assertIsInstance(result["performance_gain"], float)

    @unittest.skipIf(_FULL_DEPS, "test only relevant without numpy/scipy")
    def test_optimize_raises_parameter_error_without_numpy(self):
        from parameter_optimizer import ParameterError
        params = _make_params(1.0, 2.0)
        opt = ParameterOptimizer(params)
        with self.assertRaises(ParameterError):
            opt.optimize()


class TestParameterOptimizerInstantiation(unittest.TestCase):

    def test_stores_parameters(self):
        params = _make_params(3.0, 7.0)
        opt = ParameterOptimizer(params)
        self.assertIs(opt.parameters, params)

    def test_bounds_computed_at_init(self):
        params = _make_params(0.0)
        opt = ParameterOptimizer(params)
        self.assertIsInstance(opt.bounds, list)


if __name__ == "__main__":
    unittest.main()
