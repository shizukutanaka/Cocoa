"""Tests for avatar_personality_tuner module."""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestPersonalityProfile(unittest.TestCase):
    def test_creation(self):
        from avatar_personality_tuner import PersonalityProfile
        p = PersonalityProfile(user_id="u1")
        self.assertEqual(p.user_id, "u1")
        self.assertIsInstance(p.speaking_style, dict)

    def test_confidence_default(self):
        from avatar_personality_tuner import PersonalityProfile
        p = PersonalityProfile(user_id="u2")
        self.assertEqual(p.confidence_score, 0.0)
        self.assertEqual(p.samples_analyzed, 0)


class TestBehaviorSample(unittest.TestCase):
    def test_creation(self):
        from avatar_personality_tuner import BehaviorSample
        s = BehaviorSample(
            sample_id="s1",
            user_id="u1",
            content_type="text",
            content="Hello there!",
        )
        self.assertEqual(s.content_type, "text")
        self.assertEqual(s.analysis_results, {})


class TestTunedAvatarConfig(unittest.TestCase):
    def test_creation(self):
        from avatar_personality_tuner import TunedAvatarConfig, PersonalityProfile
        profile = PersonalityProfile(user_id="u1")
        cfg = TunedAvatarConfig(
            user_id="u1",
            base_avatar_id="base_av",
            personality_profile=profile,
        )
        self.assertEqual(cfg.user_id, "u1")
        self.assertEqual(cfg.optimized_settings, {})


class TestPersonalityAnalyzer(unittest.TestCase):
    def _make(self):
        with patch('avatar_personality_tuner.get_security_manager', return_value=MagicMock()):
            from avatar_personality_tuner import PersonalityAnalyzer
            return PersonalityAnalyzer()

    def test_init(self):
        pa = self._make()
        self.assertIsNotNone(pa)

    def test_emotion_keywords(self):
        pa = self._make()
        self.assertIsInstance(pa.emotion_keywords, dict)
        self.assertIn("happy", pa.emotion_keywords)


class TestAvatarPersonalityTuner(unittest.TestCase):
    def _make(self):
        with patch('avatar_personality_tuner.get_security_manager', return_value=MagicMock()):
            from avatar_personality_tuner import AvatarPersonalityTuner
            with patch('pathlib.Path.mkdir'):
                return AvatarPersonalityTuner()

    def test_init(self):
        tuner = self._make()
        self.assertIsNotNone(tuner)

    def test_get_tuner_factory(self):
        import inspect
        from avatar_personality_tuner import get_avatar_personality_tuner
        self.assertTrue(inspect.iscoroutinefunction(get_avatar_personality_tuner))


if __name__ == '__main__':
    unittest.main()
