"""Tests for vr_ar_avatar_system module."""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


def _make_vr_config(avatar_id="test_avatar"):
    from vr_ar_avatar_system import VRAvatarConfig
    return VRAvatarConfig(
        avatar_id=avatar_id,
        user_id="user_1",
        vr_model="default.glb",
        animation_profile="idle",
        haptic_settings={"enabled": True},
        interaction_zones=[],
        metaverse_compatibility=["vrc", "ovr"],
        performance_mode="balanced",
    )


class TestVRAvatarConfig(unittest.TestCase):
    def test_creation(self):
        cfg = _make_vr_config()
        self.assertEqual(cfg.avatar_id, "test_avatar")
        self.assertEqual(cfg.user_id, "user_1")

    def test_custom_avatar_id(self):
        cfg = _make_vr_config("my_avatar")
        self.assertEqual(cfg.avatar_id, "my_avatar")


class TestARInteractionData(unittest.TestCase):
    def test_creation(self):
        from vr_ar_avatar_system import ARInteractionData
        data = ARInteractionData(
            gesture_type="wave",
            confidence_score=0.95,
            hand_position={"x": 1.0, "y": 2.0, "z": 3.0},
            eye_tracking={"gaze_x": 0.1, "gaze_y": 0.2},
            voice_commands=["hello"],
            environmental_context={"room_scale": True},
        )
        self.assertEqual(data.gesture_type, "wave")
        self.assertAlmostEqual(data.confidence_score, 0.95)


class TestVRAvatarSystem(unittest.TestCase):
    def _make(self):
        with patch('vr_ar_avatar_system.get_security_manager', return_value=MagicMock()):
            from vr_ar_avatar_system import VRAvatarSystem
            return VRAvatarSystem()

    def test_init(self):
        svc = self._make()
        self.assertIsNotNone(svc)

    def test_supported_vr_platforms(self):
        svc = self._make()
        self.assertIsInstance(svc.supported_vr_platforms, list)
        self.assertGreater(len(svc.supported_vr_platforms), 0)

    def test_animation_profiles(self):
        svc = self._make()
        self.assertIsInstance(svc.animation_profiles, dict)
        self.assertIn("realistic", svc.animation_profiles)

    def test_security_manager_set(self):
        svc = self._make()
        self.assertIsNotNone(svc.security_manager)


if __name__ == '__main__':
    unittest.main()
