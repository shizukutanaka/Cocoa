"""Acceptance tests for scripts/generate_languages_improved.py.

Spec: docs/SPEC_GENERATE_LANGUAGES.md (REQ-GL-01..04, improved variant)
Runnable without pytest:  python3 -m unittest tests.test_generate_languages_improved -v

Loaded by explicit path under a unique module name: this module shares the
class name LanguageFileGenerator with generate_languages.py, so a bare import
would risk resolving to the wrong module in the full suite.
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC = PROJECT_ROOT / "scripts" / "generate_languages_improved.py"
_spec = importlib.util.spec_from_file_location("cocoa_generate_languages_improved", _SRC)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["cocoa_generate_languages_improved"] = _mod
_spec.loader.exec_module(_mod)

LanguageFileGenerator = _mod.LanguageFileGenerator


class TestInit(unittest.TestCase):
    def test_creates_nested_locales_dir(self):
        """REQ-GL-01: nested parents must be created."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x" / "y" / "locales"
            LanguageFileGenerator(locales_dir=str(path))
            self.assertTrue(path.exists())


class TestImprovedTranslate(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.g = LanguageFileGenerator(locales_dir=str(Path(self._td.name) / "l"))

    def tearDown(self):
        self._td.cleanup()

    def test_dutch_known_phrase(self):
        self.assertEqual(self.g._improved_translate("Home", "nl", "Dutch"), "Startpagina")

    def test_japanese_known_phrase(self):
        self.assertEqual(self.g._improved_translate("Settings", "ja", "Japanese"), "設定")

    def test_english_passthrough(self):
        self.assertEqual(self.g._improved_translate("Home", "en", "English"), "Home")

    def test_unknown_lang_returns_original(self):
        """REQ-GL-03: unknown lang code falls back to source text."""
        self.assertEqual(self.g._improved_translate("Home", "zz", "Unknown"), "Home")

    def test_unknown_phrase_returns_original(self):
        self.assertEqual(self.g._improved_translate("XyzPhrase", "nl", "Dutch"), "XyzPhrase")


class TestTranslateContent(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.g = LanguageFileGenerator(locales_dir=str(Path(self._td.name) / "l"))

    def tearDown(self):
        self._td.cleanup()

    def test_preserves_structure_and_non_strings(self):
        content = {"title": "Home", "meta": {"Version": "Version", "n": 7, "b": False}}
        result = self.g._translate_content(content, "nl", "Dutch")
        self.assertEqual(result["title"], "Startpagina")
        self.assertEqual(result["meta"]["Version"], "Versie")
        self.assertEqual(result["meta"]["n"], 7)
        self.assertIs(result["meta"]["b"], False)

    def test_translates_list_items(self):
        content = {"nav": ["Home", "Settings", "Help"]}
        result = self.g._translate_content(content, "nl", "Dutch")
        self.assertEqual(result["nav"], ["Startpagina", "Instellingen", "Help"])


class TestCreateLanguageFile(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.locales = Path(self._td.name) / "locales"
        self.g = LanguageFileGenerator(locales_dir=str(self.locales))

    def tearDown(self):
        self._td.cleanup()

    def test_creates_new_file(self):
        ok = self.g.create_language_file("nl", "Dutch", {"title": "Home"})
        self.assertTrue(ok)
        data = json.loads((self.locales / "nl.json").read_text(encoding="utf-8"))
        self.assertEqual(data["title"], "Startpagina")

    def test_skips_existing_file(self):
        existing = self.locales / "nl.json"
        existing.write_text('{"keep": 1}', encoding="utf-8")
        ok = self.g.create_language_file("nl", "Dutch", {"title": "Home"})
        self.assertTrue(ok)
        self.assertEqual(json.loads(existing.read_text(encoding="utf-8")), {"keep": 1})


class TestLoadEnglishTemplate(unittest.TestCase):
    def test_missing_template_raises(self):
        with tempfile.TemporaryDirectory() as td:
            g = LanguageFileGenerator(locales_dir=str(Path(td) / "locales"))
            with self.assertRaises(FileNotFoundError):
                g.load_english_template()


if __name__ == "__main__":
    unittest.main(verbosity=2)
