"""Tests for voice_cloning module."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestVoiceSample(unittest.TestCase):
    def test_creation(self):
        from voice_cloning import VoiceSample
        vs = VoiceSample(
            sample_id="s1",
            user_id="u1",
            audio_path="/tmp/a.wav",
            duration=5.0,
            sample_rate=22050,
        )
        self.assertEqual(vs.sample_id, "s1")
        self.assertIsNotNone(vs.created_at)


class TestVoiceCloneRequest(unittest.TestCase):
    def test_creation(self):
        from voice_cloning import VoiceCloneRequest
        req = VoiceCloneRequest(user_id="u1", voice_name="MyVoice", sample_audio_paths=["/a.wav"])
        self.assertEqual(req.voice_name, "MyVoice")
        self.assertEqual(req.quality_preference, "balanced")


class TestVoiceCloneResult(unittest.TestCase):
    def test_success(self):
        from voice_cloning import VoiceCloneResult
        r = VoiceCloneResult(success=True, voice_id="v1", voice_name="MyVoice", model_path="/models/v1")
        self.assertTrue(r.success)

    def test_failure_defaults(self):
        from voice_cloning import VoiceCloneResult
        r = VoiceCloneResult(success=False, voice_id="x", voice_name="x")
        self.assertIsInstance(r.quality_metrics, dict)


class TestVoiceCloningEngine(unittest.TestCase):
    def _make_engine(self):
        with patch('voice_cloning.get_security_manager', return_value=MagicMock()):
            from voice_cloning import VoiceCloningEngine
            return VoiceCloningEngine()

    def test_init(self):
        eng = self._make_engine()
        self.assertIsNotNone(eng)

    def test_clone_voice_is_async(self):
        import inspect

        from voice_cloning import VoiceCloningEngine
        self.assertTrue(inspect.iscoroutinefunction(VoiceCloningEngine.clone_voice))

    def test_generate_speech_is_async(self):
        import inspect

        from voice_cloning import VoiceCloningEngine
        self.assertTrue(inspect.iscoroutinefunction(VoiceCloningEngine.generate_speech))

    def test_list_user_voices_is_async(self):
        import inspect

        from voice_cloning import VoiceCloningEngine
        self.assertTrue(inspect.iscoroutinefunction(VoiceCloningEngine.list_user_voices))


class TestVoiceCloningFactory(unittest.TestCase):
    def test_factory_is_async(self):
        import inspect

        from voice_cloning import get_voice_cloning_engine
        self.assertTrue(inspect.iscoroutinefunction(get_voice_cloning_engine))


if __name__ == '__main__':
    unittest.main()
