"""Acceptance tests for i18n.py locale normalization, fallback chain, and t() fix.

Spec: docs/SPEC_I18N.md (REQ-I18N-03..06)
Runnable without pytest:  python3 -m unittest tests.test_i18n -v
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

import i18n as i18n_mod  # noqa: E402
from i18n import _normalize_lang, I18N  # noqa: E402


class TestNormalizeLang(unittest.TestCase):
    def test_posix_to_bcp47(self):
        self.assertEqual(_normalize_lang("zh_TW"), "zh-tw")
        self.assertEqual(_normalize_lang("PT_BR"), "pt-br")
        self.assertEqual(_normalize_lang("zh_CN"), "zh-cn")

    def test_already_lowercase(self):
        self.assertEqual(_normalize_lang("en"), "en")
        self.assertEqual(_normalize_lang("zh-tw"), "zh-tw")

    def test_mixed_case(self):
        self.assertEqual(_normalize_lang("JA"), "ja")
        self.assertEqual(_normalize_lang("EN_US"), "en-us")

    def test_empty_string(self):
        self.assertEqual(_normalize_lang(""), "")


class TestLoadTranslationFallback(unittest.TestCase):
    """Use a temp locales dir to test the fallback chain without touching repo files."""

    def _make_locales(self, tmpdir, files: dict):
        for name, data in files.items():
            path = os.path.join(tmpdir, f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)

    def setUp(self):
        # Clear class-level cache before each test
        I18N._translation_cache.clear()

    def _make_i18n(self, lang, locales_dir):
        with patch.object(i18n_mod, "LOCALES_DIR", locales_dir):
            obj = I18N(lang=lang)
        return obj

    def test_exact_match(self):
        with tempfile.TemporaryDirectory() as d:
            self._make_locales(d, {"zh-tw": {"hello": "你好"}, "zh": {"hello": "你好(简)"}, "en": {"hello": "Hello"}})
            obj = self._make_i18n("zh-tw", d)
        self.assertEqual(obj.t("hello"), "你好")

    def test_fallback_to_language_prefix(self):
        # zh-tw.json absent → should load zh.json
        with tempfile.TemporaryDirectory() as d:
            self._make_locales(d, {"zh": {"hello": "你好(简)"}, "en": {"hello": "Hello"}})
            obj = self._make_i18n("zh-tw", d)
        self.assertEqual(obj.t("hello"), "你好(简)")

    def test_fallback_to_en(self):
        # neither zh-tw.json nor zh.json → load en.json
        with tempfile.TemporaryDirectory() as d:
            self._make_locales(d, {"en": {"hello": "Hello"}})
            obj = self._make_i18n("zh-tw", d)
        self.assertEqual(obj.t("hello"), "Hello")

    def test_fallback_to_empty(self):
        # no files at all
        with tempfile.TemporaryDirectory() as d:
            obj = self._make_i18n("zh-tw", d)
        self.assertEqual(obj.translations, {})

    def test_en_loaded_directly(self):
        with tempfile.TemporaryDirectory() as d:
            self._make_locales(d, {"en": {"greeting": "Hi"}})
            obj = self._make_i18n("en", d)
        self.assertEqual(obj.t("greeting"), "Hi")


class TestTMethod(unittest.TestCase):
    def setUp(self):
        I18N._translation_cache.clear()

    def _make_i18n_with_data(self, data: dict) -> I18N:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "en.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            with patch.object(i18n_mod, "LOCALES_DIR", d):
                obj = I18N(lang="en")
        return obj

    def test_found_key(self):
        obj = self._make_i18n_with_data({"title": "My App"})
        self.assertEqual(obj.t("title"), "My App")

    def test_missing_key_returns_key(self):
        obj = self._make_i18n_with_data({})
        self.assertEqual(obj.t("missing_key"), "missing_key")

    def test_missing_key_with_default(self):
        obj = self._make_i18n_with_data({})
        self.assertEqual(obj.t("missing_key", default="fallback"), "fallback")

    def test_default_empty_string_is_respected(self):
        # BUG FIX: old code: `default or key` → `"" or key` → returned key
        obj = self._make_i18n_with_data({})
        self.assertEqual(obj.t("missing_key", default=""), "")

    def test_default_none_returns_key(self):
        obj = self._make_i18n_with_data({})
        # With default=None (the Python default), key itself is returned
        self.assertEqual(obj.t("missing_key", default=None), "missing_key")


class TestGetFont(unittest.TestCase):
    def setUp(self):
        I18N._translation_cache.clear()

    def _make_i18n(self, lang, locales_dir):
        with patch.object(i18n_mod, "LOCALES_DIR", locales_dir):
            obj = I18N(lang=lang)
        return obj

    def test_exact_font_lookup(self):
        with tempfile.TemporaryDirectory() as d:
            obj = self._make_i18n("ja", d)
        font_name = obj.get_font()[0]
        self.assertEqual(font_name, "Yu Gothic UI")

    def test_zh_tw_font(self):
        with tempfile.TemporaryDirectory() as d:
            obj = self._make_i18n("zh-tw", d)
        font_name = obj.get_font()[0]
        self.assertEqual(font_name, "Microsoft JhengHei")

    def test_zh_cn_falls_back_to_zh(self):
        # zh-cn not in FONT_MAP, but zh is
        with tempfile.TemporaryDirectory() as d:
            obj = self._make_i18n("zh-cn", d)
        font_name = obj.get_font()[0]
        self.assertEqual(font_name, "Noto Sans SC")  # zh font

    def test_unknown_lang_returns_arial(self):
        with tempfile.TemporaryDirectory() as d:
            obj = self._make_i18n("xx", d)
        self.assertEqual(obj.get_font()[0], "Arial")

    def test_get_font_size_weight(self):
        with tempfile.TemporaryDirectory() as d:
            obj = self._make_i18n("en", d)
        self.assertEqual(obj.get_font(16, "bold"), ("Arial", 16, "bold"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
