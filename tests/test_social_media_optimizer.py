"""Tests for social_media_optimizer module."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestPlatformSpec(unittest.TestCase):
    def _make(self):
        from social_media_optimizer import PlatformSpec
        return PlatformSpec(
            platform_id="youtube",
            name="YouTube",
            max_duration=43200,
            max_file_size=128000,
            resolutions=[(1920, 1080), (1280, 720)],
            aspect_ratios=["16:9"],
            video_codecs=["libx264"],
            audio_codecs=["aac"],
            frame_rates=[30, 60],
            bitrates={"1080p": "8000k"},
        )

    def test_creation(self):
        spec = self._make()
        self.assertEqual(spec.platform_id, "youtube")

    def test_special_requirements_default(self):
        spec = self._make()
        self.assertEqual(spec.special_requirements, {})

    def test_custom_special_requirements(self):
        from social_media_optimizer import PlatformSpec
        spec = PlatformSpec(
            platform_id="x",
            name="X",
            max_duration=140,
            max_file_size=512,
            resolutions=[(1280, 720)],
            aspect_ratios=["16:9"],
            video_codecs=["libx264"],
            audio_codecs=["aac"],
            frame_rates=[30],
            bitrates={"720p": "2000k"},
            special_requirements={"watermark": False},
        )
        self.assertFalse(spec.special_requirements["watermark"])


class TestOptimizationRequest(unittest.TestCase):
    def test_defaults(self):
        from social_media_optimizer import OptimizationRequest
        req = OptimizationRequest(
            video_path="/tmp/video.mp4",
            platforms=["youtube", "instagram"],
        )
        self.assertEqual(req.priority, "balanced")
        self.assertEqual(req.custom_settings, {})

    def test_custom_priority(self):
        from social_media_optimizer import OptimizationRequest
        req = OptimizationRequest(
            video_path="/tmp/video.mp4",
            platforms=["tiktok"],
            priority="speed",
        )
        self.assertEqual(req.priority, "speed")


class TestOptimizationResult(unittest.TestCase):
    def test_creation(self):
        from social_media_optimizer import OptimizationResult
        result = OptimizationResult(success=True)
        self.assertTrue(result.success)
        self.assertEqual(result.optimized_videos, {})

    def test_defaults(self):
        from social_media_optimizer import OptimizationResult
        result = OptimizationResult(success=False, error_message="test error")
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "test error")


class TestSocialMediaOptimizer(unittest.TestCase):
    def _make_optimizer(self):
        from social_media_optimizer import SocialMediaOptimizer
        with patch('social_media_optimizer.get_security_manager', return_value=MagicMock()):
            return SocialMediaOptimizer()

    def test_init(self):
        opt = self._make_optimizer()
        self.assertIsNotNone(opt)

    def test_platform_specs_populated(self):
        opt = self._make_optimizer()
        self.assertIn("youtube", opt.platform_specs)
        self.assertIn("instagram", opt.platform_specs)

    def test_get_supported_platforms(self):
        opt = self._make_optimizer()
        platforms = opt.get_supported_platforms()
        self.assertIsInstance(platforms, list)
        self.assertGreater(len(platforms), 0)

    def test_get_platform_spec(self):
        opt = self._make_optimizer()
        spec = opt.get_platform_spec("youtube")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.platform_id, "youtube")

    def test_get_platform_spec_unknown(self):
        opt = self._make_optimizer()
        spec = opt.get_platform_spec("unknown_platform_xyz")
        self.assertIsNone(spec)

    def test_youtube_spec_has_valid_resolutions(self):
        opt = self._make_optimizer()
        spec = opt.get_platform_spec("youtube")
        self.assertIsInstance(spec.resolutions, list)
        self.assertTrue(any(r[0] >= 1280 for r in spec.resolutions))

    def test_tiktok_spec_short_max_duration(self):
        opt = self._make_optimizer()
        spec = opt.get_platform_spec("tiktok")
        if spec:
            self.assertLessEqual(spec.max_duration, 600)


class TestEncodingPresetFallback(unittest.TestCase):
    def test_fallback_encoding_preset(self):
        from social_media_optimizer import EncodingPreset
        preset = EncodingPreset(preset_id="test", name="Test")
        self.assertEqual(preset.video_codec, "libx264")
        self.assertEqual(preset.fps, 30)


class TestOptimizeForPlatformsUnsupportedPlatform(unittest.IsolatedAsyncioTestCase):
    """optimize_for_platforms must not IndexError when unsupported platforms are mixed in.

    Bug: tasks[] was built only for supported platforms, but results were
    indexed by enumerate(request.platforms) which included unsupported ids,
    causing platform_results[i] to go out of bounds.
    Fix: build supported_platforms list first, then zip() with platform_results.
    """

    def _make_optimizer(self):
        from social_media_optimizer import SocialMediaOptimizer
        opt = SocialMediaOptimizer.__new__(SocialMediaOptimizer)
        opt.initialized = True
        opt.platform_specs = {}
        opt.output_dir = __import__('pathlib').Path('/tmp')
        opt.video_encoder = None
        return opt

    async def test_unsupported_platform_does_not_crash(self):
        import asyncio
        from social_media_optimizer import OptimizationRequest, SocialMediaOptimizer
        opt = self._make_optimizer()
        # Only youtube is "supported"
        from social_media_optimizer import PlatformSpec
        opt.platform_specs = {
            "youtube": PlatformSpec(
                platform_id="youtube", name="YouTube",
                max_duration=43200, max_file_size=128000,
                resolutions=[(1920, 1080)], aspect_ratios=["16:9"],
                video_codecs=["libx264"], audio_codecs=["aac"],
                frame_rates=[30], bitrates={"1080p": "8000k"},
            )
        }
        opt.initialized = False

        async def fake_init():
            opt.initialized = True

        opt.initialize = fake_init

        async def fake_optimize(video_path, pid, priority, custom):
            return {"success": True, "output_path": "/tmp/out.mp4",
                    "thumbnail_path": None, "file_size": 0,
                    "compression_ratio": 1.0, "quality_score": 1.0,
                    "platform_spec": {}}

        opt._optimize_single_platform = fake_optimize

        req = OptimizationRequest(
            video_path="/tmp/test.mp4",
            platforms=["unsupported_xyz", "youtube", "another_bad"],
        )
        result = await opt.optimize_for_platforms(req)
        # Should succeed, only youtube in optimized_videos
        self.assertTrue(result.success)
        self.assertIn("youtube", result.metadata["platform_results"])
        self.assertNotIn("unsupported_xyz", result.metadata["platform_results"])

    async def test_all_unsupported_returns_empty_success(self):
        from social_media_optimizer import OptimizationRequest
        opt = self._make_optimizer()

        async def fake_init():
            pass

        opt.initialize = fake_init

        req = OptimizationRequest(
            video_path="/tmp/test.mp4",
            platforms=["fake1", "fake2"],
        )
        result = await opt.optimize_for_platforms(req)
        self.assertTrue(result.success)
        self.assertEqual(result.metadata["successful_optimizations"], 0)


if __name__ == '__main__':
    unittest.main()
