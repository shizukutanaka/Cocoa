"""Regression tests for fixes made during the repair/hardening pass.

Runnable without pytest (stdlib unittest only), since this environment has
no pytest and the cryptography native binding panics on import:

    python3 -m unittest tests.test_repairs -v

Covers three earlier fixes:
  1. i18n_manager: SUPPORTED_LANGUAGES must have no duplicate keys (F601).
  2. validate_and_repair_presets: reconstructed repair_preset/validate_and_repair_dir.
  3. run_tests: run_suite returns an (int, result) tuple (exit-code contract).
"""
import ast
import io
import json
import sys
import contextlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_DIR = PROJECT_ROOT / "main"
for p in (str(PROJECT_ROOT), str(MAIN_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


class TestI18nNoDuplicateKeys(unittest.TestCase):
    """SUPPORTED_LANGUAGES had ti/so/om duplicated and a 9-language block
    copy-pasted 4 times; assert the dict literal has unique keys."""

    def test_supported_languages_unique(self):
        src = (MAIN_DIR / "i18n_manager.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        biggest = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                keys = [k.value for k in node.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)]
                if biggest is None or len(keys) > len(biggest):
                    biggest = keys
        self.assertIsNotNone(biggest)
        self.assertGreater(len(biggest), 50, "expected the language registry dict")
        dups = sorted({k for k in biggest if biggest.count(k) > 1})
        self.assertEqual(dups, [], f"duplicate language codes: {dups}")


class TestPresetRepair(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module("validate_and_repair_presets")

    def test_repair_preset_adds_required_keys(self):
        out = self.mod.repair_preset({})
        self.assertEqual(out["name"], "unknown")
        self.assertEqual(out["parameters"], [])

    def test_repair_preset_fixes_parameters_type(self):
        out = self.mod.repair_preset({"name": "x", "parameters": "not-a-list"})
        self.assertEqual(out["parameters"], [])
        self.assertEqual(out["name"], "x")  # existing value preserved

    def test_repair_preset_preserves_valid(self):
        valid = {"name": "ok", "parameters": [{"k": 1}]}
        out = self.mod.repair_preset(dict(valid))
        self.assertEqual(out, valid)

    def test_validate_and_repair_dir_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "presets"
            target.mkdir()
            broken = target / "broken.json"
            broken.write_text(json.dumps({"parameters": "bad"}), encoding="utf-8")

            reports = self.mod.validate_and_repair_dir(str(target), str(Path(d) / "backups"))

            self.assertEqual(len(reports), 1)
            entry = reports[0]
            self.assertIsNone(entry["error"])
            self.assertTrue(entry["repaired"])
            fixed = json.loads(broken.read_text(encoding="utf-8"))
            self.assertEqual(fixed["parameters"], [])
            self.assertEqual(fixed["name"], "unknown")
            self.assertIn("backup", entry)


class TestRunSuiteContract(unittest.TestCase):
    """run_suite must return (int_exit_code, TestResult); run_selected_tests/
    run_all_tests rely on this to produce a valid sys.exit() code."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("run_tests", str(PROJECT_ROOT / "run_tests.py"))
        cls.rt = importlib.util.module_from_spec(spec)
        sys.modules["run_tests"] = cls.rt
        spec.loader.exec_module(cls.rt)

    def _suite(self, passing: bool):
        outer = self

        class _T(unittest.TestCase):
            def test_case(self):
                outer.assertTrue(True) if passing else self.fail("intentional")
        s = unittest.TestSuite()
        s.addTest(_T("test_case"))
        return s

    def _run_suite_quiet(self, suite):
        """Run a suite via run_suite while suppressing the inner runner's
        stdout/stderr (otherwise an intentional sub-failure pollutes output)."""
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return self.rt.run_suite(suite, verbosity=0)

    def test_run_suite_returns_int_tuple_on_success(self):
        code, result = self._run_suite_quiet(self._suite(True))
        self.assertIsInstance(code, int)
        self.assertEqual(code, 0)
        self.assertTrue(result.wasSuccessful())

    def test_run_suite_returns_nonzero_on_failure(self):
        code, result = self._run_suite_quiet(self._suite(False))
        self.assertIsInstance(code, int)
        self.assertEqual(code, 1)
        self.assertFalse(result.wasSuccessful())


if __name__ == "__main__":
    unittest.main(verbosity=2)
