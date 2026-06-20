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


class TestBatchOptimizeExceptionIsolation(unittest.IsolatedAsyncioTestCase):
    """batch_optimize must not abort all requests when one task raises.

    Bug: asyncio.gather(*tasks) without return_exceptions=True propagates the
    first exception immediately, cancelling all pending tasks and leaving the
    caller with a partially-populated (and unordered) results list.
    Fix: return_exceptions=True + collect results via return values, not a
    shared-list side-effect.
    """

    def _make_optimizer(self):
        from social_media_optimizer import SocialMediaOptimizer
        with patch('social_media_optimizer.get_security_manager', return_value=MagicMock()):
            opt = SocialMediaOptimizer()
        return opt

    async def test_one_failing_task_does_not_abort_others(self):
        from social_media_optimizer import OptimizationRequest, OptimizationResult
        opt = self._make_optimizer()

        call_count = 0

        async def fake_optimize(request):
            nonlocal call_count
            call_count += 1
            if request.video_path == "/tmp/bad.mp4":
                raise RuntimeError("simulated failure")
            return OptimizationResult(
                success=True,
                optimized_videos={},
                metadata={"platform_results": {}, "successful_optimizations": 0},
            )

        opt.optimize_for_platforms = fake_optimize

        requests = [
            OptimizationRequest(video_path="/tmp/good1.mp4", platforms=["youtube"]),
            OptimizationRequest(video_path="/tmp/bad.mp4", platforms=["youtube"]),
            OptimizationRequest(video_path="/tmp/good2.mp4", platforms=["youtube"]),
        ]
        results = await opt.batch_optimize(requests, max_concurrent=3)
        # All three tasks should have been attempted
        self.assertEqual(call_count, 3)
        # Failed task is dropped; two successes remain
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.success for r in results))

    async def test_all_succeed_returns_all(self):
        from social_media_optimizer import OptimizationRequest, OptimizationResult
        opt = self._make_optimizer()

        async def fake_optimize(request):
            return OptimizationResult(
                success=True,
                optimized_videos={},
                metadata={"platform_results": {}, "successful_optimizations": 0},
            )

        opt.optimize_for_platforms = fake_optimize
        requests = [
            OptimizationRequest(video_path=f"/tmp/v{i}.mp4", platforms=["youtube"])
            for i in range(4)
        ]
        results = await opt.batch_optimize(requests, max_concurrent=2)
        self.assertEqual(len(results), 4)


if __name__ == '__main__':
    unittest.main()
