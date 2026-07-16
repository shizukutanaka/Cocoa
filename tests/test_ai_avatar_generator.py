"""Tests for ai_avatar_generator module."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestAvatarGenerationRequest(unittest.TestCase):
    def test_required_only(self):
        from ai_avatar_generator import AvatarGenerationRequest
        req = AvatarGenerationRequest(user_id="u1")
        self.assertEqual(req.user_id, "u1")
        self.assertEqual(req.style, "realistic")
        self.assertEqual(req.quality, "high")

    def test_with_prompt(self):
        from ai_avatar_generator import AvatarGenerationRequest
        req = AvatarGenerationRequest(user_id="u2", prompt="anime style avatar")
        self.assertEqual(req.prompt, "anime style avatar")

    def test_customizations_default(self):
        from ai_avatar_generator import AvatarGenerationRequest
        req = AvatarGenerationRequest(user_id="u3")
        self.assertEqual(req.customizations, {})


class TestAvatarGenerationResult(unittest.TestCase):
    def test_success(self):
        from ai_avatar_generator import AvatarGenerationResult
        result = AvatarGenerationResult(success=True, avatar_path="/tmp/avatar.png")
        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)

    def test_failure(self):
        from ai_avatar_generator import AvatarGenerationResult
        result = AvatarGenerationResult(success=False, error_message="out of memory")
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "out of memory")

    def test_metadata_default(self):
        from ai_avatar_generator import AvatarGenerationResult
        result = AvatarGenerationResult(success=True)
        self.assertEqual(result.metadata, {})


class TestAvatarStyle(unittest.TestCase):
    def test_constants(self):
        from ai_avatar_generator import AvatarStyle
        self.assertEqual(AvatarStyle.REALISTIC, "realistic")
        self.assertEqual(AvatarStyle.ANIME, "anime")
        self.assertEqual(AvatarStyle.PROFESSIONAL, "professional")


class TestAIAvatarGeneratorInit(unittest.TestCase):
    def test_init_no_model(self):
        with patch('ai_avatar_generator.get_security_manager', return_value=MagicMock()):
            from ai_avatar_generator import AIAvatarGenerator
            gen = AIAvatarGenerator()
            self.assertIsNotNone(gen)

    def test_get_generator_is_async(self):
        import inspect

        from ai_avatar_generator import get_ai_avatar_generator
        self.assertTrue(inspect.iscoroutinefunction(get_ai_avatar_generator))


if __name__ == '__main__':
    unittest.main()
