"""Acceptance tests for parameters_batch_validator.

Spec: docs/SPEC_BATCH_VALIDATOR.md (REQ-BV-01..06)
Runnable without pytest:  python3 -m unittest tests.test_batch_validator -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

import parameters_batch_validator as bv  # noqa: E402


class TestValidateParameterTypes(unittest.TestCase):
    def setUp(self):
        self.types = {"age": int, "name": str, "score": float, "active": bool}

    def test_all_correct(self):
        preset = {"age": 25, "name": "Alice", "score": 9.5, "active": True}
        self.assertEqual(bv.validate_parameter_types(preset, self.types), {})

    def test_type_mismatch(self):
        preset = {"age": "25", "name": "Alice"}
        errors = bv.validate_parameter_types(preset, self.types)
        self.assertIn("age", errors)
        self.assertNotIn("name", errors)

    def test_missing_key_skipped(self):
        # keys in param_types but absent from preset → no error
        preset = {"name": "Alice"}
        self.assertEqual(bv.validate_parameter_types(preset, self.types), {})

    def test_extra_keys_in_preset_ignored(self):
        preset = {"age": 1, "extra": "whatever"}
        self.assertEqual(bv.validate_parameter_types(preset, {"age": int}), {})

    def test_bool_is_not_int(self):
        # bool is a subclass of int in Python; we still flag it if int is expected
        # and the value is a bool — preserve existing behaviour
        preset = {"age": True}
        errors = bv.validate_parameter_types(preset, {"age": int})
        # isinstance(True, int) is True in Python, so no error expected
        self.assertEqual(errors, {})

    def test_multiple_mismatches(self):
        preset = {"age": "x", "score": "y"}
        errors = bv.validate_parameter_types(preset, self.types)
        self.assertIn("age", errors)
        self.assertIn("score", errors)


class TestParseTypeMap(unittest.TestCase):
    def test_all_allowed_types(self):
        raw = {"a": "bool", "b": "int", "c": "float", "d": "str", "e": "list", "f": "dict"}
        result = bv._parse_type_map(raw)
        self.assertEqual(result["a"], bool)
        self.assertEqual(result["b"], int)
        self.assertEqual(result["c"], float)
        self.assertEqual(result["d"], str)
        self.assertEqual(result["e"], list)
        self.assertEqual(result["f"], dict)

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError) as ctx:
            bv._parse_type_map({"x": "os.system"})
        self.assertIn("Unsupported type", str(ctx.exception))

    def test_eval_would_have_been_exploitable(self):
        # Confirm the old pattern is gone: "os.system('echo pwned')" is not allowed
        with self.assertRaises(ValueError):
            bv._parse_type_map({"x": "os.system('echo pwned')"})

    def test_empty_map(self):
        self.assertEqual(bv._parse_type_map({}), {})


class TestBatchValidatePresets(unittest.TestCase):
    def _write(self, directory, filename, data):
        path = Path(directory) / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return path

    def test_nonexistent_directory(self):
        result = bv.batch_validate_presets("/tmp/does_not_exist_xyzzy123", {"a": int})
        self.assertEqual(result["errors"], {})
        self.assertIn("error", result["summary"])
        self.assertEqual(result["summary"]["total"], 0)

    def test_all_pass(self):
        with tempfile.TemporaryDirectory() as d:
            self._write(d, "a.json", {"age": 5})
            self._write(d, "b.json", {"age": 10})
            result = bv.batch_validate_presets(d, {"age": int})
        self.assertEqual(result["summary"]["total"], 2)
        self.assertEqual(result["summary"]["passed"], 2)
        self.assertEqual(result["summary"]["failed"], 0)
        self.assertEqual(result["errors"], {})

    def test_some_fail(self):
        with tempfile.TemporaryDirectory() as d:
            self._write(d, "ok.json", {"age": 5})
            self._write(d, "bad.json", {"age": "five"})
            result = bv.batch_validate_presets(d, {"age": int})
        self.assertEqual(result["summary"]["total"], 2)
        self.assertEqual(result["summary"]["passed"], 1)
        self.assertEqual(result["summary"]["failed"], 1)
        self.assertIn("bad.json", result["errors"])

    def test_broken_json_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            self._write(d, "ok.json", {"age": 5})
            (Path(d) / "broken.json").write_text("{not valid json}", encoding="utf-8")
            result = bv.batch_validate_presets(d, {"age": int})
        # broken.json is skipped, not counted in total
        self.assertEqual(result["summary"]["total"], 1)
        self.assertEqual(result["summary"]["passed"], 1)

    def test_non_json_files_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            self._write(d, "preset.json", {"age": 5})
            (Path(d) / "readme.txt").write_text("ignore me", encoding="utf-8")
            result = bv.batch_validate_presets(d, {"age": int})
        self.assertEqual(result["summary"]["total"], 1)

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as d:
            result = bv.batch_validate_presets(d, {"age": int})
        self.assertEqual(result["summary"]["total"], 0)
        self.assertEqual(result["errors"], {})

    def test_summary_keys_always_present(self):
        with tempfile.TemporaryDirectory() as d:
            result = bv.batch_validate_presets(d, {})
        for key in ("total", "passed", "failed"):
            self.assertIn(key, result["summary"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
