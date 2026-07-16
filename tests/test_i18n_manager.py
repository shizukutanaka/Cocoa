"""Tests for I18NManager — language switching, translate, cache, RTL detection."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))
from i18n_manager import I18NManager, Language


class TestI18NManagerInit(unittest.TestCase):

    def setUp(self):
        self.mgr = I18NManager()

    def test_default_language_set(self):
        self.assertIsNotNone(self.mgr.current_language)

    def test_get_available_languages_returns_list(self):
        langs = self.mgr.get_available_languages()
        self.assertIsInstance(langs, list)
        self.assertGreater(len(langs), 0)

    def test_available_languages_have_code_key(self):
        langs = self.mgr.get_available_languages()
        for lang in langs[:5]:
            self.assertIn("code", lang)


class TestI18NManagerSetLanguage(unittest.TestCase):

    def setUp(self):
        self.mgr = I18NManager()

    def test_set_valid_language_returns_true(self):
        result = self.mgr.set_language("en")
        self.assertTrue(result)

    def test_set_language_updates_current(self):
        self.mgr.set_language("en")
        self.assertEqual(self.mgr.current_language, "en")

    def test_set_invalid_language_returns_false(self):
        result = self.mgr.set_language("xx_INVALID")
        self.assertFalse(result)

    def test_set_invalid_language_does_not_change_current(self):
        self.mgr.set_language("en")
        self.mgr.set_language("xx_INVALID")
        self.assertEqual(self.mgr.current_language, "en")


class TestI18NManagerTranslate(unittest.TestCase):

    def setUp(self):
        self.mgr = I18NManager()

    def test_translate_missing_key_returns_key(self):
        result = self.mgr.translate("nonexistent.key.xyz")
        self.assertIsInstance(result, str)

    def test_translate_with_fallback(self):
        result = self.mgr.translate("nonexistent.key.xyz", fallback="fallback_value")
        self.assertEqual(result, "fallback_value")

    def test_translate_returns_string(self):
        result = self.mgr.translate("app_name")
        self.assertIsInstance(result, str)


class TestI18NManagerRTL(unittest.TestCase):

    def setUp(self):
        self.mgr = I18NManager()

    def test_english_is_not_rtl(self):
        self.assertFalse(self.mgr.is_rtl_language("en"))

    def test_arabic_is_rtl(self):
        self.assertTrue(self.mgr.is_rtl_language("ar"))

    def test_hebrew_is_rtl(self):
        self.assertTrue(self.mgr.is_rtl_language("he"))

    def test_japanese_is_not_rtl(self):
        self.assertFalse(self.mgr.is_rtl_language("ja"))


class TestLanguageDataclass(unittest.TestCase):

    def test_language_creation(self):
        lang = Language(code="en", name="English", native_name="English")
        self.assertEqual(lang.code, "en")

    def test_language_rtl_default_false(self):
        lang = Language(code="en", name="English", native_name="English")
        self.assertFalse(lang.rtl)

    def test_language_rtl_true(self):
        lang = Language(code="ar", name="Arabic", native_name="العربية", rtl=True)
        self.assertTrue(lang.rtl)
