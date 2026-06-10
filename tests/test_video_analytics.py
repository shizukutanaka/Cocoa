"""Tests for video_analytics module."""
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestVideoEvent(unittest.TestCase):
    def test_creation(self):
        from video_analytics import VideoEvent
        event = VideoEvent(
            event_id="e1", video_id="v1", user_id="u1",
            event_type="play", position=0.0,
            timestamp=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
        )
        self.assertEqual(event.event_type, "play")

    def test_metadata_default(self):
        from video_analytics import VideoEvent
        event = VideoEvent(
            event_id="e2", video_id="v1", user_id="u1",
            event_type="pause", position=10.5,
            timestamp=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
        )
        self.assertEqual(event.metadata, {})


class TestVideoMetrics(unittest.TestCase):
    def test_creation(self):
        from video_analytics import VideoMetrics
        m = VideoMetrics(video_id="v1")
        self.assertEqual(m.video_id, "v1")
        self.assertEqual(m.total_views, 0)

    def test_defaults(self):
        from video_analytics import VideoMetrics
        m = VideoMetrics(video_id="v2")
        self.assertEqual(m.completion_rate, 0.0)
        self.assertIsInstance(m.drop_off_points, list)


class TestAnalyticsReport(unittest.TestCase):
    def test_creation(self):
        from datetime import datetime, timedelta, timezone

        from video_analytics import AnalyticsReport
        now = datetime.now(timezone.utc)
        r = AnalyticsReport(
            report_id="r1",
            video_id="v1",
            report_type="weekly",
            start_date=now - timedelta(days=7),
            end_date=now,
            metrics={},
            insights=["insight1"],
        )
        self.assertEqual(r.report_id, "r1")
        self.assertIsInstance(r.insights, list)


class TestVideoAnalyticsServiceAsync(unittest.IsolatedAsyncioTestCase):
    async def _make(self, tmpdir):
        with patch('video_analytics.get_security_manager', return_value=MagicMock()):
            from video_analytics import VideoAnalyticsService
            svc = VideoAnalyticsService.__new__(VideoAnalyticsService)
            svc.security_manager = MagicMock()
            svc.db_path = os.path.join(tmpdir, "analytics.db")
            import queue
            import threading
            svc.event_queue = queue.Queue()
            svc.metrics_cache = {}
            svc.cache_lock = threading.Lock()
            svc.is_running = False
            svc.is_processing = False
            svc.processing_thread = None
            svc.cache_ttl = 300
            svc.batch_size = 100
            await svc._init_database()
            return svc

    async def test_init_database(self):
        with tempfile.TemporaryDirectory() as d:
            svc = await self._make(d)
            self.assertTrue(os.path.exists(svc.db_path))  # noqa: ASYNC240

    async def test_get_video_metrics_empty(self):
        with tempfile.TemporaryDirectory() as d:
            from video_analytics import VideoMetrics
            svc = await self._make(d)
            m = await svc.get_video_metrics("nonexistent_video")
            # Returns default VideoMetrics when not found
            self.assertIsInstance(m, VideoMetrics)
            self.assertEqual(m.total_views, 0)

    async def test_calculate_engagement_score_zero(self):
        with tempfile.TemporaryDirectory() as d:
            from video_analytics import VideoMetrics
            svc = await self._make(d)
            m = VideoMetrics(video_id="v1")
            score = svc._calculate_engagement_score(m)
            self.assertIsInstance(score, float)
            self.assertGreaterEqual(score, 0.0)

    async def test_analyze_drop_off_empty(self):
        with tempfile.TemporaryDirectory() as d:
            svc = await self._make(d)
            result = svc._analyze_drop_off_points([])
            self.assertIsInstance(result, dict)


if __name__ == '__main__':
    unittest.main()
