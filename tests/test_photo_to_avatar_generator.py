"""Tests for photo_to_avatar_generator module."""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestPhotoToAvatarRequest(unittest.TestCase):
    def test_creation(self):
        from photo_to_avatar_generator import PhotoToAvatarRequest
        req = PhotoToAvatarRequest(user_id="u1", source_photo_path="/tmp/photo.jpg")
        self.assertEqual(req.user_id, "u1")
        self.assertEqual(req.target_style, "realistic")

    def test_defaults(self):
        from photo_to_avatar_generator import PhotoToAvatarRequest
        req = PhotoToAvatarRequest(user_id="u", source_photo_path="/p.jpg")
        self.assertIsInstance(req.output_formats, list)
        self.assertIn("png", req.output_formats)


class TestPhotoToAvatarResult(unittest.TestCase):
    def test_success(self):
        from photo_to_avatar_generator import PhotoToAvatarResult
        r = PhotoToAvatarResult(success=True, avatar_paths={"png": "/out.png"})
        self.assertTrue(r.success)
        self.assertEqual(r.avatar_paths["png"], "/out.png")

    def test_defaults(self):
        from photo_to_avatar_generator import PhotoToAvatarResult
        r = PhotoToAvatarResult(success=False)
        self.assertIsInstance(r.avatar_paths, dict)
        self.assertIsInstance(r.facial_features, dict)


class TestPhotoToAvatarGenerator(unittest.TestCase):
    def _make_generator(self):
        with patch('photo_to_avatar_generator.get_security_manager', return_value=MagicMock()):
            from photo_to_avatar_generator import PhotoToAvatarGenerator
            return PhotoToAvatarGenerator()

    def test_init(self):
        gen = self._make_generator()
        self.assertIsNotNone(gen)

    def test_style_prompt_lookup(self):
        gen = self._make_generator()
        prompt = gen._get_style_prompt("realistic")
        self.assertIsInstance(prompt, str)
        self.assertTrue(len(prompt) > 0)

    def test_generate_is_async(self):
        import inspect
        from photo_to_avatar_generator import PhotoToAvatarGenerator
        self.assertTrue(inspect.iscoroutinefunction(PhotoToAvatarGenerator.generate_avatar_from_photo))


class TestFaceFeatureExtractor(unittest.TestCase):
    def test_init(self):
        from photo_to_avatar_generator import FaceFeatureExtractor
        fe = FaceFeatureExtractor()
        self.assertIsNotNone(fe)

    def test_face_shape_unknown(self):
        from photo_to_avatar_generator import FaceFeatureExtractor
        fe = FaceFeatureExtractor()
        result = fe._analyze_face_shape({})
        self.assertEqual(result, "unknown")

    def test_nose_features_empty(self):
        from photo_to_avatar_generator import FaceFeatureExtractor
        fe = FaceFeatureExtractor()
        result = fe._analyze_nose_features({})
        self.assertEqual(result, {})

    def test_mouth_features_empty(self):
        from photo_to_avatar_generator import FaceFeatureExtractor
        fe = FaceFeatureExtractor()
        result = fe._analyze_mouth_features({})
        self.assertEqual(result, {})


if __name__ == '__main__':
    unittest.main()
