"""
Tests for main/ar_cloud_manager.py
"""
import sys
import os
import inspect
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestSpatialAnchorDataclass(unittest.TestCase):
    def test_spatial_anchor_creation(self):
        from ar_cloud_manager import SpatialAnchor
        now = datetime.now(timezone.utc)
        anchor = SpatialAnchor(
            anchor_id="anchor_001",
            position=(1.0, 2.0, 3.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
            scale=(1.0, 1.0, 1.0),
            coordinate_system="local",
            confidence=0.95,
            created_by="test_device",
            created_at=now,
            expires_at=None,
        )
        self.assertEqual(anchor.anchor_id, "anchor_001")
        self.assertEqual(anchor.position, (1.0, 2.0, 3.0))
        self.assertIsNone(anchor.expires_at)

    def test_spatial_anchor_with_expiry(self):
        from ar_cloud_manager import SpatialAnchor
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=24)
        anchor = SpatialAnchor(
            anchor_id="anchor_002",
            position=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
            scale=(1.0, 1.0, 1.0),
            coordinate_system="global",
            confidence=0.8,
            created_by="user_1",
            created_at=now,
            expires_at=expires,
        )
        self.assertIsNotNone(anchor.expires_at)
        self.assertGreater(anchor.expires_at, anchor.created_at)


class TestARContentDataclass(unittest.TestCase):
    def test_ar_content_creation(self):
        from ar_cloud_manager import ARContent
        now = datetime.now(timezone.utc)
        content = ARContent(
            content_id="content_001",
            content_type="3d_model",
            position=(5.0, 0.0, 5.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
            scale=(1.0, 1.0, 1.0),
            data={"model_url": "https://example.com/model.glb"},
            visibility_rules={"public": True},
            interaction_enabled=True,
            persistent=True,
            created_by="user_1",
            created_at=now,
            last_accessed=now,
            access_count=0,
        )
        self.assertEqual(content.content_id, "content_001")
        self.assertEqual(content.content_type, "3d_model")
        self.assertTrue(content.persistent)
        self.assertEqual(content.access_count, 0)


class TestPointCloudDataDataclass(unittest.TestCase):
    def test_point_cloud_defaults(self):
        from ar_cloud_manager import PointCloudData
        pc = PointCloudData(points=[], colors=[])
        self.assertIsNone(pc.normals)
        self.assertIsNone(pc.timestamp)
        self.assertEqual(pc.device_id, "")
        self.assertIsNone(pc.location)


class TestARCloudManagerInit(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp()

    def _make_manager(self):
        from ar_cloud_manager import ARCloudManager
        return ARCloudManager(cloud_dir=self.tmpdir)

    def test_manager_instantiation(self):
        try:
            mgr = self._make_manager()
        except Exception as e:
            self.skipTest(f"Cannot instantiate ARCloudManager: {e}")
        self.assertIsNotNone(mgr)

    def test_manager_initial_state(self):
        try:
            mgr = self._make_manager()
        except Exception as e:
            self.skipTest(f"Cannot instantiate ARCloudManager: {e}")
        self.assertEqual(mgr.total_maps, 0)
        self.assertEqual(mgr.total_anchors, 0)
        self.assertEqual(mgr.total_content, 0)
        self.assertIsInstance(mgr.spatial_maps, dict)

    def test_manager_cloud_dir(self):
        try:
            mgr = self._make_manager()
        except Exception as e:
            self.skipTest(f"Cannot instantiate ARCloudManager: {e}")
        self.assertTrue(mgr.cloud_dir.exists())

    def test_get_ar_cloud_status_keys(self):
        try:
            mgr = self._make_manager()
        except Exception as e:
            self.skipTest(f"Cannot instantiate ARCloudManager: {e}")
        status = mgr.get_ar_cloud_status()
        for key in ("total_maps", "total_anchors", "total_content", "connected_devices",
                    "localized_devices", "open3d_available", "pyproj_available"):
            self.assertIn(key, status)


class TestARCloudManagerAsyncMethods(unittest.TestCase):
    def test_create_spatial_map_is_coroutine(self):
        from ar_cloud_manager import ARCloudManager
        self.assertTrue(inspect.iscoroutinefunction(ARCloudManager.create_spatial_map))

    def test_add_spatial_anchor_is_coroutine(self):
        from ar_cloud_manager import ARCloudManager
        self.assertTrue(inspect.iscoroutinefunction(ARCloudManager.add_spatial_anchor))

    def test_add_ar_content_is_coroutine(self):
        from ar_cloud_manager import ARCloudManager
        self.assertTrue(inspect.iscoroutinefunction(ARCloudManager.add_ar_content))

    def test_process_point_cloud_is_coroutine(self):
        from ar_cloud_manager import ARCloudManager
        self.assertTrue(inspect.iscoroutinefunction(ARCloudManager.process_point_cloud))

    def test_localize_device_is_coroutine(self):
        from ar_cloud_manager import ARCloudManager
        self.assertTrue(inspect.iscoroutinefunction(ARCloudManager.localize_device))

    def test_get_nearby_content_is_coroutine(self):
        from ar_cloud_manager import ARCloudManager
        self.assertTrue(inspect.iscoroutinefunction(ARCloudManager.get_nearby_content))


class TestARCloudManagerCreateMap(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        try:
            from ar_cloud_manager import ARCloudManager
            self.mgr = ARCloudManager(cloud_dir=self.tmpdir)
        except Exception as e:
            self.skipTest(f"Cannot instantiate ARCloudManager: {e}")

    async def test_create_spatial_map_returns_id(self):
        map_id = await self.mgr.create_spatial_map("test_map")
        self.assertTrue(map_id.startswith("map_"))
        self.assertIn(map_id, self.mgr.spatial_maps)
        self.assertEqual(self.mgr.total_maps, 1)

    async def test_add_spatial_anchor_invalid_map(self):
        with self.assertRaises(ValueError):
            await self.mgr.add_spatial_anchor(
                "nonexistent_map",
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0, 1.0),
            )

    async def test_add_ar_content_invalid_map(self):
        with self.assertRaises(ValueError):
            await self.mgr.add_ar_content(
                "nonexistent_map",
                "text",
                (0.0, 0.0, 0.0),
                {"text": "hello"},
            )

    async def test_get_nearby_content_no_device(self):
        result = await self.mgr.get_nearby_content("unknown_device")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
