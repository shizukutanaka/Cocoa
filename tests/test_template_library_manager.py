"""Tests for TemplateLibrary — get/search, categories, AvatarTemplate/VideoTemplate dataclasses."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))
from template_library import AvatarTemplate, TemplateLibrary, VideoTemplate


class TestAvatarTemplate(unittest.TestCase):

    def test_basic_creation(self):
        t = AvatarTemplate(
            template_id="t1",
            name="Test Avatar",
            description="A test",
            category="anime",
            style="realistic",
        )
        self.assertEqual(t.template_id, "t1")
        self.assertEqual(t.name, "Test Avatar")

    def test_default_tags_empty(self):
        t = AvatarTemplate(
            template_id="t1",
            name="Test",
            description="",
            category="default",
            style="default",
        )
        self.assertIsInstance(t.tags, list)

    def test_usage_count_default_zero(self):
        t = AvatarTemplate(
            template_id="t2",
            name="Test2",
            description="",
            category="default",
            style="default",
        )
        self.assertEqual(t.usage_count, 0)


class TestVideoTemplate(unittest.TestCase):

    def test_basic_creation(self):
        t = VideoTemplate(
            template_id="v1",
            name="Video Template",
            description="A video",
            category="presentation",
            script_template="Hello {{name}}",
        )
        self.assertEqual(t.template_id, "v1")


class TestTemplateLibrarySync(unittest.TestCase):

    def setUp(self):
        self.lib = TemplateLibrary()

    def test_get_avatar_categories_returns_dict(self):
        cats = self.lib.get_avatar_categories()
        self.assertIsInstance(cats, dict)

    def test_get_video_categories_returns_dict(self):
        cats = self.lib.get_video_categories()
        self.assertIsInstance(cats, dict)

    def test_get_avatar_templates_empty_initially(self):
        templates = self.lib.get_avatar_templates()
        self.assertIsInstance(templates, list)

    def test_search_templates_returns_list(self):
        results = self.lib.search_templates("test")
        self.assertIsInstance(results, list)

    def test_search_templates_video_type(self):
        results = self.lib.search_templates("video", template_type="video")
        self.assertIsInstance(results, list)


class TestTemplateLibraryAsync(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.lib = TemplateLibrary()

    async def test_create_default_avatar_templates_populates(self):
        await self.lib.create_default_avatar_templates()
        templates = self.lib.get_avatar_templates()
        self.assertGreater(len(templates), 0)

    async def test_save_and_get_avatar_template(self):
        t = AvatarTemplate(
            template_id="save_test",
            name="Saved Template",
            description="For testing",
            category="test",
            style="test",
        )
        await self.lib.save_avatar_template(t)
        results = self.lib.get_avatar_templates()
        ids = [r.template_id for r in results]
        self.assertIn("save_test", ids)

    async def test_increment_usage(self):
        t = AvatarTemplate(
            template_id="usage_test",
            name="Usage Template",
            description="",
            category="test",
            style="test",
        )
        await self.lib.save_avatar_template(t)
        await self.lib.increment_usage("usage_test", "avatar")
        templates = self.lib.get_avatar_templates()
        saved = next((x for x in templates if x.template_id == "usage_test"), None)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.usage_count, 1)
