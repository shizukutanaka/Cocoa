"""Behavioural tests for ConfigValidator.validate_from_dict.

Runnable without pytest:  python3 -m unittest tests.test_validation -v

These exercise the real default validation rules (required fields, type,
regex pattern, allowed-values) and the documented return contract
{valid, errors, warnings, config} where config is None when invalid.
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from config_validator import ConfigValidator  # noqa: E402

BASE = {
    "app_name": "Cocoa",
    "version": "1.0.0",
    "language": "ja",
    "debug": False,
    "log_level": "INFO",
}


class TestConfigValidator(unittest.TestCase):
    def setUp(self):
        self.v = ConfigValidator()

    def _result(self, cfg):
        return self.v.validate_from_dict(cfg)

    def test_minimal_valid(self):
        r = self._result(dict(BASE))
        self.assertTrue(r["valid"], r["errors"])
        self.assertEqual(r["errors"], [])
        self.assertIsNotNone(r["config"])
        # validated config preserves the input values
        self.assertEqual(r["config"]["app_name"], "Cocoa")

    def test_missing_required_field(self):
        cfg = {k: v for k, v in BASE.items() if k != "app_name"}
        r = self._result(cfg)
        self.assertFalse(r["valid"])
        self.assertTrue(any("app_name" in e for e in r["errors"]))
        self.assertIsNone(r["config"])  # config is withheld when invalid

    def test_bad_version_pattern(self):
        cfg = dict(BASE, version="1.0")  # not X.Y.Z
        self.assertFalse(self._result(cfg)["valid"])

    def test_disallowed_enum_value(self):
        cfg = dict(BASE, language="fr")  # only ja/en allowed
        self.assertFalse(self._result(cfg)["valid"])

    def test_wrong_type(self):
        cfg = dict(BASE, debug="yes")  # must be boolean
        self.assertFalse(self._result(cfg)["valid"])

    def test_log_level_enum_accepts_valid(self):
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            with self.subTest(level=level):
                self.assertTrue(self._result(dict(BASE, log_level=level))["valid"])

    def test_result_shape(self):
        r = self._result(dict(BASE))
        self.assertEqual(set(r), {"valid", "errors", "warnings", "config"})
        self.assertIsInstance(r["errors"], list)
        self.assertIsInstance(r["warnings"], list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
