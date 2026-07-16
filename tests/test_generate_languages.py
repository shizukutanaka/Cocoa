"""Acceptance tests for scripts/generate_languages.py.

Spec: docs/SPEC_GENERATE_LANGUAGES.md (REQ-GL-01..04)
Runnable without pytest:  python3 -m unittest tests.test_generate_languages -v
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

from generate_languages import LanguageFileGenerator


class TestInit(unittest.TestCase):
    def test_creates_locales_dir(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "locales"
            LanguageFileGenerator(locales_dir=str(path))
            self.assertTrue(path.exists())

    def test_creates_nested_locales_dir(self):
        """REQ-GL-01: nested parents must be created."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "a" / "b" / "locales"
            LanguageFileGenerator(locales_dir=str(path))
            self.assertTrue(path.exists())

    def test_language_map_populated(self):
        with tempfile.TemporaryDirectory() as td:
            g = LanguageFileGenerator(locales_dir=str(Path(td) / "l"))
            self.assertIn("nl", g.language_map)
            self.assertGreater(len(g.language_map), 10)


class TestSimpleTranslate(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.g = LanguageFileGenerator(locales_dir=str(Path(self._td.name) / "l"))

    def tearDown(self):
        self._td.cleanup()

    def test_japanese_known_phrase(self):
        self.assertEqual(self.g._simple_translate("Home", "ja", "Japanese"), "ホーム")

    def test_spanish_known_phrase(self):
        self.assertEqual(self.g._simple_translate("Settings", "es", "Spanish"), "Configuración")

    def test_english_passthrough(self):
        self.assertEqual(self.g._simple_translate("Home", "en", "English"), "Home")

    def test_unknown_lang_returns_original(self):
        """REQ-GL-03: unknown lang code falls back to source text."""
        self.assertEqual(self.g._simple_translate("Home", "xx", "Unknown"), "Home")

    def test_unknown_phrase_returns_original(self):
        self.assertEqual(
            self.g._simple_translate("SomeUntranslatedPhrase", "ja", "Japanese"),
            "SomeUntranslatedPhrase",
        )


class TestTranslateContent(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.g = LanguageFileGenerator(locales_dir=str(Path(self._td.name) / "l"))

    def tearDown(self):
        self._td.cleanup()

    def test_translates_top_level_string(self):
        result = self.g._translate_content({"k": "Home"}, "ja", "Japanese")
        self.assertEqual(result["k"], "ホーム")

    def test_preserves_nested_dict_structure(self):
        content = {"outer": {"inner": "Settings"}}
        result = self.g._translate_content(content, "ja", "Japanese")
        self.assertEqual(result["outer"]["inner"], "設定")

    def test_preserves_list_structure(self):
        content = {"items": ["Home", "Help"]}
        result = self.g._translate_content(content, "ja", "Japanese")
        self.assertEqual(result["items"], ["ホーム", "ヘルプ"])

    def test_preserves_non_string_values(self):
        content = {"count": 5, "flag": True, "nothing": None, "ratio": 1.5}
        result = self.g._translate_content(content, "ja", "Japanese")
        self.assertEqual(result["count"], 5)
        self.assertIs(result["flag"], True)
        self.assertIsNone(result["nothing"])
        self.assertEqual(result["ratio"], 1.5)

    def test_deeply_nested_mixed(self):
        content = {"a": {"b": ["Home", {"c": "Settings"}], "n": 3}}
        result = self.g._translate_content(content, "ja", "Japanese")
        self.assertEqual(result["a"]["b"][0], "ホーム")
        self.assertEqual(result["a"]["b"][1]["c"], "設定")
        self.assertEqual(result["a"]["n"], 3)


class TestCreateLanguageFile(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.locales = Path(self._td.name) / "locales"
        self.g = LanguageFileGenerator(locales_dir=str(self.locales))

    def tearDown(self):
        self._td.cleanup()

    def test_creates_new_file(self):
        ok = self.g.create_language_file("ja", "Japanese", {"title": "Home"})
        self.assertTrue(ok)
        out = self.locales / "ja.json"
        self.assertTrue(out.exists())
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(data["title"], "ホーム")

    def test_skips_existing_file(self):
        """REQ-GL-04: existing file is left untouched, returns True."""
        existing = self.locales / "ja.json"
        existing.write_text('{"preserve": "me"}', encoding="utf-8")
        ok = self.g.create_language_file("ja", "Japanese", {"title": "Home"})
        self.assertTrue(ok)
        # Content unchanged
        data = json.loads(existing.read_text(encoding="utf-8"))
        self.assertEqual(data, {"preserve": "me"})


class TestLoadEnglishTemplate(unittest.TestCase):
    def test_missing_template_raises(self):
        with tempfile.TemporaryDirectory() as td:
            g = LanguageFileGenerator(locales_dir=str(Path(td) / "locales"))
            with self.assertRaises(FileNotFoundError):
                g.load_english_template()

    def test_loads_existing_template(self):
        with tempfile.TemporaryDirectory() as td:
            locales = Path(td) / "locales"
            g = LanguageFileGenerator(locales_dir=str(locales))
            (locales / "en.json").write_text('{"app": "Avatar"}', encoding="utf-8")
            template = g.load_english_template()
            self.assertEqual(template["app"], "Avatar")


if __name__ == "__main__":
    unittest.main(verbosity=2)
