"""
Tests for main/vrchat_sdk_integration.py
"""

import inspect
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


with patch.dict('sys.modules', {
    'integrated_security': MagicMock(get_security_manager=MagicMock(return_value=MagicMock())),
    'requests': MagicMock(),
    'PIL': MagicMock(),
    'PIL.Image': MagicMock(),
}):
    import vrchat_sdk_integration as vr


class TestVRChatAvatarDescriptorDataclass(unittest.TestCase):

    def test_creation_stores_all_fields(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        desc = vr.VRChatAvatarDescriptor(
            name="TestAvatar",
            description="A test avatar",
            avatar_id="avt_001",
            version=1,
            author_id="usr_123",
            image_url="https://example.com/img.png",
            unity_package_url="https://example.com/pkg.unitypackage",
            created_at=now,
            updated_at=now,
        )
        self.assertEqual(desc.name, "TestAvatar")
        self.assertEqual(desc.avatar_id, "avt_001")
        self.assertEqual(desc.version, 1)


class TestVRChatAvatarParametersDataclass(unittest.TestCase):

    def test_default_values(self):
        params = vr.VRChatAvatarParameters()
        self.assertTrue(params.eye_look)
        self.assertTrue(params.eye_blink)
        self.assertTrue(params.mouth_viseme)
        self.assertEqual(params.gesture_override, "Default")
        self.assertEqual(params.locomotion, "Default")
        self.assertEqual(params.performance_rank, "Medium")
        self.assertEqual(params.shader_complexity, "Medium")
        self.assertEqual(params.texture_memory, 0)
        self.assertEqual(params.polygon_count, 0)

    def test_custom_values(self):
        params = vr.VRChatAvatarParameters(
            eye_look=False, performance_rank="Excellent", polygon_count=12000
        )
        self.assertFalse(params.eye_look)
        self.assertEqual(params.performance_rank, "Excellent")
        self.assertEqual(params.polygon_count, 12000)


class TestVRChatSDKManagerInit(unittest.TestCase):

    def _make_manager(self, api_key=None, user_id=None):
        with patch('vrchat_sdk_integration.get_security_manager', return_value=MagicMock()):
            return vr.VRChatSDKManager(api_key=api_key, user_id=user_id)

    def test_init_sets_base_url(self):
        mgr = self._make_manager()
        self.assertEqual(mgr.base_url, "https://api.vrchat.cloud/api/1")

    def test_init_sdk_version(self):
        mgr = self._make_manager()
        self.assertEqual(mgr.sdk_version, "3.0.0")

    def test_init_compatible_unity_versions(self):
        mgr = self._make_manager()
        self.assertIn("2019.4", mgr.compatible_unity_versions)
        self.assertIn("2021.3", mgr.compatible_unity_versions)

    def test_init_explicit_credentials_stored(self):
        mgr = self._make_manager(api_key="mykey", user_id="myuser")
        self.assertEqual(mgr.api_key, "mykey")
        self.assertEqual(mgr.user_id, "myuser")


class TestVRChatSDKManagerMethods(unittest.TestCase):

    def _make_manager(self):
        with patch('vrchat_sdk_integration.get_security_manager', return_value=MagicMock()):
            return vr.VRChatSDKManager(api_key="k", user_id="u")

    def test_calculate_performance_rank_poor_when_issues(self):
        mgr = self._make_manager()
        rank = mgr._calculate_performance_rank({}, ["some issue"], [])
        self.assertEqual(rank, "Poor")

    def test_calculate_performance_rank_excellent_low_memory(self):
        mgr = self._make_manager()
        rank = mgr._calculate_performance_rank(
            {'texture_memory': 10000000}, [], []
        )
        self.assertEqual(rank, "Excellent")

    def test_generate_vrchat_metadata_returns_dict(self):
        mgr = self._make_manager()
        metadata = mgr._generate_vrchat_metadata({'performance_rank': 'Good'})
        self.assertIn('name', metadata)
        self.assertIn('tags', metadata)
        self.assertIn('cocoa', metadata['tags'])
        self.assertEqual(metadata['authorId'], "u")

    def test_async_methods_are_coroutines(self):
        for method_name in ['validate_vrchat_credentials', 'export_avatar_for_vrchat',
                            'get_sdk_compatibility_info', 'upload_to_vrchat']:
            method = getattr(vr.VRChatSDKManager, method_name)
            self.assertTrue(
                inspect.iscoroutinefunction(method),
                f"{method_name} should be a coroutine function",
            )

    def test_get_sdk_compatibility_info_is_coroutine(self):
        self.assertTrue(
            inspect.iscoroutinefunction(vr.VRChatSDKManager.get_sdk_compatibility_info)
        )

    def test_get_vrchat_sdk_manager_is_coroutine(self):
        self.assertTrue(inspect.iscoroutinefunction(vr.get_vrchat_sdk_manager))


if __name__ == '__main__':
    unittest.main()
