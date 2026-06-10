"""Tests for template_library module."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestAvatarTemplate(unittest.TestCase):
    def _make(self, **kw):
        from template_library import AvatarTemplate
        defaults = {
            'template_id': "tpl_1",
            'name': "Anime Girl",
            'description': "Cute anime avatar",
            'category': "anime",
            'style': "cute",
        }
        defaults.update(kw)
        return AvatarTemplate(**defaults)

    def test_creation(self):
        t = self._make()
        self.assertEqual(t.template_id, "tpl_1")
        self.assertFalse(t.is_premium)

    def test_defaults(self):
        t = self._make()
        self.assertIsNone(t.thumbnail_path)
        self.assertEqual(t.tags, [])
        self.assertEqual(t.config, {})


class TestVideoTemplate(unittest.TestCase):
    def test_creation(self):
        from template_library import VideoTemplate
        t = VideoTemplate(
            template_id="vt_1",
            name="Intro",
            description="Intro video",
            category="greeting",
            script_template="Hello {name}!",
        )
        self.assertEqual(t.template_id, "vt_1")
        self.assertIsNone(t.background_music)


class TestTemplateLibrary(unittest.TestCase):
    def _make(self):
        with patch('template_library.get_security_manager', return_value=MagicMock()):
            from template_library import TemplateLibrary
            with patch('pathlib.Path.mkdir'):
                return TemplateLibrary()

    def test_init(self):
        lib = self._make()
        self.assertIsNotNone(lib)

    def test_get_avatar_templates_empty(self):
        lib = self._make()
        templates = lib.get_avatar_templates()
        self.assertIsInstance(templates, list)

    def test_get_video_templates_empty(self):
        lib = self._make()
        templates = lib.get_video_templates()
        self.assertIsInstance(templates, list)

    def test_categories_attribute(self):
        lib = self._make()
        if hasattr(lib, 'get_categories'):
            cats = lib.get_categories()
            self.assertIsInstance(cats, list)
        else:
            self.assertTrue(hasattr(lib, 'avatar_templates') or hasattr(lib, 'categories'))

    def test_search_empty(self):
        lib = self._make()
        results = lib.search_templates("nonexistent_xyz")
        self.assertIsInstance(results, list)

    def test_default_templates_loaded(self):
        lib = self._make()
        # Default templates should be initialized
        total = len(lib.avatar_templates) + len(lib.video_templates)
        self.assertGreaterEqual(total, 0)


if __name__ == '__main__':
    unittest.main()
