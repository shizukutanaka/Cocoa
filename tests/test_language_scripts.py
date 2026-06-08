"""Acceptance tests for scripts/consolidate_languages.py and move_languages.py.

Spec: docs/SPEC_LANGUAGE_SCRIPTS.md (REQ-LANG-01..04)
Runnable without pytest:  python3 -m unittest tests.test_language_scripts -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from consolidate_languages import consolidate_language_files  # noqa: E402
from move_languages import move_remaining_languages  # noqa: E402


def _make_project(td, main_files=None, locales_files=None):
    root = Path(td)
    (root / "main").mkdir()
    main_files = main_files or {}
    locales_files = locales_files or {}
    for name, data in main_files.items():
        (root / "main" / name).write_text(
            json.dumps(data) if isinstance(data, (dict, list)) else data,
            encoding="utf-8",
        )
    if locales_files:
        (root / "locales").mkdir(exist_ok=True)
        for name, data in locales_files.items():
            (root / "locales" / name).write_text(
                json.dumps(data) if isinstance(data, (dict, list)) else data,
                encoding="utf-8",
            )
    return root


class TestConsolidate(unittest.TestCase):
    def test_moves_when_no_existing_locale(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(td, main_files={"de.json": {"k": "v"}})
            result = consolidate_language_files(project_root=root, lang_codes=["de"])
            self.assertEqual(result["consolidated"], 1)
            self.assertTrue((root / "locales" / "de.json").exists())
            self.assertFalse((root / "main" / "de.json").exists())

    def test_returns_expected_keys(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(td, main_files={"de.json": {}})
            result = consolidate_language_files(project_root=root, lang_codes=["de"])
            self.assertIn("consolidated", result)
            self.assertIn("skipped", result)

    def test_merges_with_locales_priority(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(
                td,
                main_files={"fr.json": {"a": "main", "b": "main_only"}},
                locales_files={"fr.json": {"a": "locale"}},
            )
            result = consolidate_language_files(project_root=root, lang_codes=["fr"])
            self.assertEqual(result["consolidated"], 1)
            merged = json.loads((root / "locales" / "fr.json").read_text(encoding="utf-8"))
            # locales value wins on conflict
            self.assertEqual(merged["a"], "locale")
            # main-only key is preserved
            self.assertEqual(merged["b"], "main_only")
            # main file removed after merge
            self.assertFalse((root / "main" / "fr.json").exists())

    def test_missing_main_file_counts_as_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(td, main_files={})
            result = consolidate_language_files(project_root=root, lang_codes=["de", "es"])
            self.assertEqual(result["consolidated"], 0)
            self.assertEqual(result["skipped"], 2)

    def test_invalid_json_merge_is_skipped_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(
                td,
                main_files={"ru.json": "{not valid json"},
                locales_files={"ru.json": {"a": 1}},
            )
            # Should not raise
            result = consolidate_language_files(project_root=root, lang_codes=["ru"])
            self.assertEqual(result["skipped"], 1)
            self.assertEqual(result["consolidated"], 0)
            # main file remains since merge failed
            self.assertTrue((root / "main" / "ru.json").exists())

    def test_creates_locales_dir_if_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(td, main_files={"de.json": {}})
            # no locales dir initially
            self.assertFalse((root / "locales").exists())
            consolidate_language_files(project_root=root, lang_codes=["de"])
            self.assertTrue((root / "locales").exists())

    def test_mixed_consolidate_and_skip(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(td, main_files={"de.json": {"x": 1}})
            result = consolidate_language_files(project_root=root, lang_codes=["de", "zz"])
            self.assertEqual(result["consolidated"], 1)
            self.assertEqual(result["skipped"], 1)


class TestMoveRemaining(unittest.TestCase):
    def test_moves_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(td, main_files={"fr.json": {"k": "v"}})
            result = move_remaining_languages(project_root=root, langs=["fr"])
            self.assertEqual(result["moved"], 1)
            self.assertTrue((root / "locales" / "fr.json").exists())
            self.assertFalse((root / "main" / "fr.json").exists())

    def test_returns_moved_key(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(td, main_files={"fr.json": {}})
            result = move_remaining_languages(project_root=root, langs=["fr"])
            self.assertIn("moved", result)

    def test_missing_file_not_counted(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(td, main_files={})
            result = move_remaining_languages(project_root=root, langs=["fr", "de"])
            self.assertEqual(result["moved"], 0)

    def test_content_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(td, main_files={"ko.json": {"hello": "안녕"}})
            move_remaining_languages(project_root=root, langs=["ko"])
            data = json.loads((root / "locales" / "ko.json").read_text(encoding="utf-8"))
            self.assertEqual(data["hello"], "안녕")

    def test_overwrites_existing_locale(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(
                td,
                main_files={"es.json": {"v": "new"}},
                locales_files={"es.json": {"v": "old"}},
            )
            move_remaining_languages(project_root=root, langs=["es"])
            data = json.loads((root / "locales" / "es.json").read_text(encoding="utf-8"))
            self.assertEqual(data["v"], "new")

    def test_creates_locales_dir_if_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(td, main_files={"fr.json": {}})
            self.assertFalse((root / "locales").exists())
            move_remaining_languages(project_root=root, langs=["fr"])
            self.assertTrue((root / "locales").exists())

    def test_multiple_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(td, main_files={
                "fr.json": {}, "de.json": {}, "ko.json": {},
            })
            result = move_remaining_languages(project_root=root, langs=["fr", "de", "ko"])
            self.assertEqual(result["moved"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
