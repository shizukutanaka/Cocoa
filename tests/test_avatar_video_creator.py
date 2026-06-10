"""
Unit tests for main/avatar_video_creator.py
"""

import os
import sys
import inspect
import unittest
from unittest.mock import MagicMock, patch
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))

# Stub heavy optional dependencies before importing the module
cv2_stub = types.ModuleType('cv2')
cv2_stub.imwrite = MagicMock(return_value=True)
cv2_stub.resize = MagicMock()
cv2_stub.cvtColor = MagicMock()
cv2_stub.COLOR_RGB2BGR = 4
sys.modules.setdefault('cv2', cv2_stub)

numpy_stub = types.ModuleType('numpy')
numpy_stub.ndarray = object
numpy_stub.full = MagicMock(return_value=MagicMock())
numpy_stub.array = MagicMock(return_value=MagicMock())
numpy_stub.uint8 = int
sys.modules.setdefault('numpy', numpy_stub)

pil_stub = types.ModuleType('PIL')
pil_image_stub = types.ModuleType('PIL.Image')
pil_draw_stub = types.ModuleType('PIL.ImageDraw')
pil_font_stub = types.ModuleType('PIL.ImageFont')
pil_image_stub.Image = MagicMock  # used as a type annotation (Image.Image)
pil_image_stub.new = MagicMock(return_value=MagicMock())
pil_image_stub.open = MagicMock(return_value=MagicMock())
pil_image_stub.fromarray = MagicMock(return_value=MagicMock())
pil_draw_stub.Draw = MagicMock(return_value=MagicMock())
pil_font_stub.truetype = MagicMock(return_value=MagicMock())
pil_font_stub.load_default = MagicMock(return_value=MagicMock())
pil_stub.Image = pil_image_stub
pil_stub.ImageDraw = pil_draw_stub
pil_stub.ImageFont = pil_font_stub
sys.modules.setdefault('PIL', pil_stub)
sys.modules.setdefault('PIL.Image', pil_image_stub)
sys.modules.setdefault('PIL.ImageDraw', pil_draw_stub)
sys.modules.setdefault('PIL.ImageFont', pil_font_stub)

mp_stub = types.ModuleType('moviepy.editor')
sys.modules.setdefault('moviepy', types.ModuleType('moviepy'))
sys.modules.setdefault('moviepy.editor', mp_stub)

# Stub integrated_security
mock_security_manager = MagicMock()
is_stub = types.ModuleType('integrated_security')
is_stub.get_security_manager = MagicMock(return_value=mock_security_manager)
sys.modules.setdefault('integrated_security', is_stub)

with patch('integrated_security.get_security_manager', return_value=mock_security_manager):
    from avatar_video_creator import (
        VideoGenerationRequest,
        VideoGenerationResult,
        AvatarVideoCreator,
        get_avatar_video_creator,
    )


class TestVideoGenerationRequest(unittest.TestCase):
    """Tests for VideoGenerationRequest dataclass"""

    def _make_request(self, **kwargs):
        defaults = dict(
            user_id="user_1",
            avatar_id="avatar_1",
            script_text="Hello world, this is a test script.",
        )
        defaults.update(kwargs)
        return VideoGenerationRequest(**defaults)

    def test_basic_creation(self):
        req = self._make_request()
        self.assertEqual(req.user_id, "user_1")
        self.assertEqual(req.avatar_id, "avatar_1")

    def test_default_voice_language(self):
        req = self._make_request()
        self.assertEqual(req.voice_language, "ja")

    def test_default_voice_gender(self):
        req = self._make_request()
        self.assertEqual(req.voice_gender, "neutral")

    def test_default_video_style(self):
        req = self._make_request()
        self.assertEqual(req.video_style, "presentation")

    def test_default_fps(self):
        req = self._make_request()
        self.assertEqual(req.fps, 30)

    def test_default_resolution(self):
        req = self._make_request()
        self.assertEqual(req.resolution, (1920, 1080))

    def test_default_duration_limit(self):
        req = self._make_request()
        self.assertEqual(req.duration_limit, 300)

    def test_default_background_music_none(self):
        req = self._make_request()
        self.assertIsNone(req.background_music)

    def test_custom_values(self):
        req = self._make_request(voice_language="en", fps=24, video_style="tutorial")
        self.assertEqual(req.voice_language, "en")
        self.assertEqual(req.fps, 24)
        self.assertEqual(req.video_style, "tutorial")


class TestVideoGenerationResult(unittest.TestCase):
    """Tests for VideoGenerationResult dataclass"""

    def test_success_result(self):
        result = VideoGenerationResult(
            success=True,
            video_path="/tmp/video.mp4",
            thumbnail_path="/tmp/thumb.jpg",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.video_path, "/tmp/video.mp4")

    def test_default_metadata_is_empty_dict(self):
        result = VideoGenerationResult(success=True)
        self.assertIsInstance(result.metadata, dict)
        self.assertEqual(len(result.metadata), 0)

    def test_default_error_message_none(self):
        result = VideoGenerationResult(success=True)
        self.assertIsNone(result.error_message)

    def test_default_generation_time(self):
        result = VideoGenerationResult(success=False)
        self.assertEqual(result.generation_time, 0.0)

    def test_failure_result(self):
        result = VideoGenerationResult(success=False, error_message="Something went wrong")
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Something went wrong")


class TestAvatarVideoCreatorInit(unittest.TestCase):
    """Tests for AvatarVideoCreator class initialization"""

    def setUp(self):
        with patch('avatar_video_creator.get_security_manager', return_value=mock_security_manager):
            self.creator = AvatarVideoCreator(assets_dir="/tmp/test_assets")

    def test_instance_created(self):
        self.assertIsInstance(self.creator, AvatarVideoCreator)

    def test_supported_languages_list(self):
        self.assertIn("ja", self.creator.supported_languages)
        self.assertIn("en", self.creator.supported_languages)
        self.assertIsInstance(self.creator.supported_languages, list)

    def test_supported_styles_list(self):
        self.assertIn("presentation", self.creator.supported_styles)
        self.assertIn("tutorial", self.creator.supported_styles)
        self.assertIn("storytelling", self.creator.supported_styles)
        self.assertIn("interview", self.creator.supported_styles)

    def test_max_duration(self):
        self.assertEqual(self.creator.max_duration, 600)

    def test_fonts_is_dict(self):
        self.assertIsInstance(self.creator.fonts, dict)

    def test_async_method_signatures(self):
        """Core generation methods should be async coroutines"""
        async_methods = [
            'generate_video',
            '_validate_request',
            '_load_avatar_image',
            '_create_default_avatar',
            '_parse_script',
            '_generate_video_frames',
            '_add_text_to_frame',
            '_create_video_from_frames',
            '_generate_thumbnail',
            'get_video_templates',
            'get_user_videos',
        ]
        for name in async_methods:
            method = getattr(self.creator, name)
            self.assertTrue(
                inspect.iscoroutinefunction(method),
                f"Expected {name} to be a coroutine function"
            )

    def test_get_avatar_video_creator_is_async(self):
        self.assertTrue(inspect.iscoroutinefunction(get_avatar_video_creator))


if __name__ == '__main__':
    unittest.main()
