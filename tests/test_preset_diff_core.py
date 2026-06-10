"""Tests for main/preset_diff_core.py."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "main"))

from preset_diff_core import (
    _json_lines,
    diff_presets,
    generate_html_diff,
    load_preset,
    save_diff_html,
    write_diff_output,
)


class TestDiffPresets(unittest.TestCase):
    def test_identical_presets_no_diff(self):
        p = {"name": "test", "version": 1}
        same, lines = diff_presets(p, p)
        self.assertTrue(same)
        self.assertEqual(lines, [])

    def test_different_presets_returns_diff(self):
        p1 = {"name": "old", "value": 1}
        p2 = {"name": "new", "value": 2}
        same, lines = diff_presets(p1, p2)
        self.assertFalse(same)
        self.assertGreater(len(lines), 0)

    def test_diff_contains_header_lines(self):
        p1 = {"a": 1}
        p2 = {"a": 2}
        _, lines = diff_presets(p1, p2, "old.json", "new.json")
        header = "\n".join(lines)
        self.assertIn("old.json", header)
        self.assertIn("new.json", header)

    def test_sort_keys_produces_sorted_json(self):
        p1 = {"z": 1, "a": 2}
        p2 = {"z": 99, "a": 2}
        _, lines = diff_presets(p1, p2, sort_keys=True)
        joined = "\n".join(lines)
        # With sort_keys=True, 'a' appears before 'z' in the output
        self.assertLess(joined.index('"a"'), joined.index('"z"'))

    def test_empty_dicts_are_same(self):
        same, lines = diff_presets({}, {})
        self.assertTrue(same)
        self.assertEqual(lines, [])


class TestJsonLines(unittest.TestCase):
    def test_returns_list_of_strings(self):
        result = _json_lines({"key": "value"}, sort_keys=False)
        self.assertIsInstance(result, list)
        self.assertTrue(all(isinstance(line, str) for line in result))

    def test_sort_keys_produces_sorted_output(self):
        payload = {"z": 1, "a": 2}
        lines = _json_lines(payload, sort_keys=True)
        combined = "\n".join(lines)
        self.assertLess(combined.index('"a"'), combined.index('"z"'))


class TestLoadPreset(unittest.TestCase):
    def test_load_valid_json(self):
        data = {"name": "test", "version": 2}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:  # noqa: SIM115
            json.dump(data, f)
            fname = f.name
        try:
            result = load_preset(fname)
            self.assertEqual(result, data)
        finally:
            os.unlink(fname)

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_preset("/nonexistent/path/preset.json")

    def test_invalid_json_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:  # noqa: SIM115
            f.write("not valid json{{{")
            fname = f.name
        try:
            with self.assertRaises(json.JSONDecodeError):
                load_preset(fname)
        finally:
            os.unlink(fname)


class TestGenerateHtmlDiff(unittest.TestCase):
    def test_returns_html_string(self):
        p1 = {"a": 1}
        p2 = {"a": 2}
        html = generate_html_diff(p1, p2, "old", "new")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("old", html)
        self.assertIn("new", html)

    def test_html_contains_diff_table(self):
        p1 = {"key": "old_value"}
        p2 = {"key": "new_value"}
        html = generate_html_diff(p1, p2, "before", "after")
        self.assertIn("<table", html.lower())


class TestSaveDiffHtml(unittest.TestCase):
    def test_saves_file(self):
        html = "<html><body>test</body></html>"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_diff_html(html, report_dir=tmpdir, open_in_browser=False)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                self.assertEqual(f.read(), html)

    def test_custom_output_path(self):
        html = "<html><body>custom</body></html>"
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "my_diff.html")
            path = save_diff_html(html, output_path=out, open_in_browser=False)
            self.assertEqual(path, out)
            self.assertTrue(os.path.exists(out))


class TestWriteDiffOutput(unittest.TestCase):
    def test_writes_to_file(self):
        lines = ["line1", "line2"]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:  # noqa: SIM115
            fname = f.name
        try:
            write_diff_output(lines, output_path=fname)
            with open(fname) as f:
                content = f.read()
            self.assertEqual(content, "line1\nline2")
        finally:
            os.unlink(fname)

    def test_directory_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir, self.assertRaises(IsADirectoryError):
            write_diff_output(["x"], output_path=tmpdir)


if __name__ == "__main__":
    unittest.main()
