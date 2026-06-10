"""Tests for virtual_backgrounds module."""
import sys
import os
import inspect
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestBackgroundTemplate(unittest.TestCase):
    def test_creation(self):
        from virtual_backgrounds import BackgroundTemplate
        bt = BackgroundTemplate(
            template_id="t1",
            name="Ocean",
            description="Ocean view",
            category="nature",
            image_path="/tmp/ocean.jpg",
        )
        self.assertEqual(bt.template_id, "t1")
        self.assertIsInstance(bt.tags, list)

    def test_defaults(self):
        from virtual_backgrounds import BackgroundTemplate
        bt = BackgroundTemplate(
            template_id="t2", name="Space", description="Space", category="sci-fi", image_path="/p.jpg"
        )
        self.assertFalse(bt.is_premium)
        self.assertIsInstance(bt.settings, dict)


class TestBackgroundConfig(unittest.TestCase):
    def test_creation(self):
        from virtual_backgrounds import BackgroundConfig
        cfg = BackgroundConfig(background_id="bg1", custom_image_path="/img.jpg")
        self.assertEqual(cfg.background_id, "bg1")

    def test_defaults(self):
        from virtual_backgrounds import BackgroundConfig
        cfg = BackgroundConfig(background_id="bg2")
        self.assertIsInstance(cfg.effects, list)
        self.assertIsInstance(cfg.branding, dict)


class TestBackgroundProcessor(unittest.TestCase):
    def test_init(self):
        from virtual_backgrounds import BackgroundProcessor
        bp = BackgroundProcessor()
        self.assertIsNotNone(bp)

    def test_apply_background_is_async(self):
        from virtual_backgrounds import BackgroundProcessor
        self.assertTrue(inspect.iscoroutinefunction(BackgroundProcessor.apply_background))


class TestVirtualBackgroundsService(unittest.TestCase):
    def test_init(self):
        with patch('virtual_backgrounds.get_security_manager', return_value=MagicMock()):
            from virtual_backgrounds import VirtualBackgroundsService
            svc = VirtualBackgroundsService()
            self.assertIsNotNone(svc)

    def test_apply_config_is_async(self):
        from virtual_backgrounds import VirtualBackgroundsService
        self.assertTrue(inspect.iscoroutinefunction(VirtualBackgroundsService.apply_background_config))

    def test_create_custom_is_async(self):
        from virtual_backgrounds import VirtualBackgroundsService
        self.assertTrue(inspect.iscoroutinefunction(VirtualBackgroundsService.create_custom_background))

    def test_factory_is_async(self):
        from virtual_backgrounds import get_virtual_backgrounds_service
        self.assertTrue(inspect.iscoroutinefunction(get_virtual_backgrounds_service))


if __name__ == '__main__':
    unittest.main()
