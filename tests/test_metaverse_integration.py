"""Tests for metaverse_integration module."""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestMetaverseAvatarRequest(unittest.TestCase):
    def _make(self, **kw):
        from metaverse_integration import MetaverseAvatarRequest
        defaults = dict(
            user_id="u1",
            avatar_id="av1",
            platform="unity",
            environment="vr",
        )
        defaults.update(kw)
        return MetaverseAvatarRequest(**defaults)

    def test_creation(self):
        req = self._make()
        self.assertEqual(req.user_id, "u1")
        self.assertEqual(req.platform, "unity")

    def test_position_default(self):
        req = self._make()
        self.assertEqual(req.position, (0.0, 0.0, 0.0))


class TestMetaverseAvatarResult(unittest.TestCase):
    def test_creation(self):
        from metaverse_integration import MetaverseAvatarResult
        result = MetaverseAvatarResult(success=True)
        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)

    def test_defaults(self):
        from metaverse_integration import MetaverseAvatarResult
        result = MetaverseAvatarResult(success=False, error_message="fail")
        self.assertEqual(result.avatar_data, {})
        self.assertEqual(result.error_message, "fail")


class TestVRARIntegration(unittest.TestCase):
    def _make(self):
        with patch('metaverse_integration.get_security_manager', return_value=MagicMock()):
            from metaverse_integration import VRARIntegration
            return VRARIntegration()

    def test_init(self):
        svc = self._make()
        self.assertIsNotNone(svc)

    def test_supported_platforms(self):
        svc = self._make()
        self.assertIsInstance(svc.supported_platforms, (list, dict))
        self.assertGreater(len(svc.supported_platforms), 0)

    def test_has_platform_data(self):
        svc = self._make()
        if isinstance(svc.supported_platforms, dict):
            self.assertIn("unity", svc.supported_platforms)
        else:
            self.assertGreater(len(svc.supported_platforms), 0)


class TestMetaverseIntegration(unittest.TestCase):
    def _make(self):
        with patch('metaverse_integration.get_security_manager', return_value=MagicMock()):
            from metaverse_integration import MetaverseIntegration
            return MetaverseIntegration()

    def test_init(self):
        svc = self._make()
        self.assertIsNotNone(svc)

    def test_platform_configs(self):
        svc = self._make()
        self.assertIsInstance(svc.platform_configs, dict)
        self.assertGreater(len(svc.platform_configs), 0)


if __name__ == '__main__':
    unittest.main()
