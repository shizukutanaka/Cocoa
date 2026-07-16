"""Tests for main/parameters_batch_validator.py."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "main"))

from parameters_batch_validator import (
    _parse_type_map,
    batch_validate_presets,
    validate_parameter_types,
)


class TestParseTypeMap(unittest.TestCase):
    def test_all_allowed_types(self):
        raw = {"flag": "bool", "count": "int", "ratio": "float", "name": "str"}
        result = _parse_type_map(raw)
        self.assertEqual(result["flag"], bool)
        self.assertEqual(result["count"], int)
        self.assertEqual(result["ratio"], float)
        self.assertEqual(result["name"], str)

    def test_list_and_dict_types(self):
        result = _parse_type_map({"items": "list", "meta": "dict"})
        self.assertEqual(result["items"], list)
        self.assertEqual(result["meta"], dict)

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _parse_type_map({"x": "datetime"})
        self.assertIn("datetime", str(ctx.exception))

    def test_empty_map(self):
        self.assertEqual(_parse_type_map({}), {})


class TestValidateParameterTypes(unittest.TestCase):
    def test_no_errors_on_match(self):
        preset = {"enabled": True, "count": 5, "name": "test"}
        types = {"enabled": bool, "count": int, "name": str}
        self.assertEqual(validate_parameter_types(preset, types), {})

    def test_type_mismatch_reported(self):
        preset = {"count": "five"}
        types = {"count": int}
        errors = validate_parameter_types(preset, types)
        self.assertIn("count", errors)
        self.assertIn("int", errors["count"])
        self.assertIn("str", errors["count"])

    def test_missing_key_skipped(self):
        preset = {}
        types = {"required_field": str}
        self.assertEqual(validate_parameter_types(preset, types), {})

    def test_extra_preset_keys_ignored(self):
        preset = {"a": 1, "b": "extra"}
        types = {"a": int}
        self.assertEqual(validate_parameter_types(preset, types), {})

    def test_bool_is_also_int(self):
        preset = {"flag": True}
        types = {"flag": bool}
        self.assertEqual(validate_parameter_types(preset, types), {})


class TestBatchValidatePresets(unittest.TestCase):
    def _write_preset(self, directory, name, data):
        path = os.path.join(directory, name)
        with open(path, "w") as f:
            json.dump(data, f)
        return path

    def test_nonexistent_directory(self):
        result = batch_validate_presets("/nonexistent/path", {})
        self.assertIn("error", result["summary"])
        self.assertEqual(result["summary"]["total"], 0)

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as d:
            result = batch_validate_presets(d, {"x": int})
            self.assertEqual(result["summary"]["total"], 0)
            self.assertEqual(result["summary"]["passed"], 0)

    def test_all_pass(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_preset(d, "a.json", {"value": 42})
            self._write_preset(d, "b.json", {"value": 10})
            result = batch_validate_presets(d, {"value": int})
            self.assertEqual(result["summary"]["total"], 2)
            self.assertEqual(result["summary"]["passed"], 2)
            self.assertEqual(result["summary"]["failed"], 0)
            self.assertEqual(result["errors"], {})

    def test_one_fail(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_preset(d, "ok.json", {"value": 5})
            self._write_preset(d, "bad.json", {"value": "not_an_int"})
            result = batch_validate_presets(d, {"value": int})
            self.assertEqual(result["summary"]["failed"], 1)
            self.assertIn("bad.json", result["errors"])
            self.assertIn("value", result["errors"]["bad.json"])

    def test_ignores_non_json_files(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_preset(d, "valid.json", {"x": 1})
            open(os.path.join(d, "readme.txt"), "w").close()
            result = batch_validate_presets(d, {"x": int})
            self.assertEqual(result["summary"]["total"], 1)

    def test_invalid_json_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "broken.json"), "w") as f:
                f.write("{not valid json")
            self._write_preset(d, "good.json", {"x": 1})
            result = batch_validate_presets(d, {"x": int})
            self.assertEqual(result["summary"]["total"], 1)

    def test_empty_types_all_pass(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_preset(d, "p.json", {"anything": "goes"})
            result = batch_validate_presets(d, {})
            self.assertEqual(result["summary"]["passed"], 1)


if __name__ == "__main__":
    unittest.main()
