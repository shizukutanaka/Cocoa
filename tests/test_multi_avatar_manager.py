"""Tests for MultiAvatarManager — scene creation, avatar management, timeline."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))
from multi_avatar_manager import (
    MultiAvatarManager, AvatarInstance, MultiAvatarScene,
)


class TestAvatarInstance(unittest.TestCase):

    def test_basic_creation(self):
        inst = AvatarInstance(
            instance_id="inst1",
            avatar_id="av1",
            name="Avatar 1",
            position=(0, 0),
            size=(100, 200),
        )
        self.assertEqual(inst.instance_id, "inst1")
        self.assertEqual(inst.avatar_id, "av1")

    def test_position_is_tuple(self):
        inst = AvatarInstance(
            instance_id="inst1",
            avatar_id="av1",
            name="Avatar 1",
            position=(100, 200),
            size=(300, 400),
        )
        self.assertEqual(inst.position, (100, 200))

    def test_z_index_default_zero(self):
        inst = AvatarInstance(
            instance_id="inst1",
            avatar_id="av1",
            name="Avatar 1",
            position=(0, 0),
            size=(100, 200),
        )
        self.assertEqual(inst.z_index, 0)


class TestMultiAvatarScene(unittest.TestCase):

    def test_basic_creation(self):
        scene = MultiAvatarScene(
            scene_id="s1",
            name="Test Scene",
            description="",
            duration=10.0,
            resolution=(1920, 1080),
        )
        self.assertEqual(scene.scene_id, "s1")
        self.assertEqual(scene.name, "Test Scene")

    def test_avatars_default_empty(self):
        scene = MultiAvatarScene(scene_id="s1", name="Test", description="", duration=10.0, resolution=(1920, 1080))
        self.assertEqual(len(scene.avatars), 0)

    def test_elements_default_empty(self):
        scene = MultiAvatarScene(scene_id="s1", name="Test", description="", duration=10.0, resolution=(1920, 1080))
        self.assertEqual(len(scene.elements), 0)


class TestMultiAvatarManagerInit(unittest.TestCase):

    def setUp(self):
        self.mgr = MultiAvatarManager()

    def test_manager_created(self):
        self.assertIsNotNone(self.mgr)

    def test_scenes_starts_empty(self):
        self.assertEqual(len(self.mgr.scenes), 0)


class TestMultiAvatarManagerAsync(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mgr = MultiAvatarManager()
        self.mgr.db_path = os.path.join(self.tmpdir, "test.db")
        await self.mgr._init_database()

    async def asyncTearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    async def test_create_scene_returns_id(self):
        scene_config = {"name": "Test Scene", "width": 1920, "height": 1080}
        scene_id = await self.mgr.create_scene(scene_config)
        self.assertIsNotNone(scene_id)
        self.assertIsInstance(scene_id, str)

    async def test_create_scene_stored_in_scenes(self):
        scene_config = {"name": "My Scene", "width": 1280, "height": 720}
        scene_id = await self.mgr.create_scene(scene_config)
        self.assertIn(scene_id, self.mgr.scenes)

    async def test_add_avatar_to_existing_scene(self):
        scene_id = await self.mgr.create_scene({"name": "Scene"})
        avatar_config = {"avatar_id": "av1", "name": "Avatar 1"}
        result = await self.mgr.add_avatar_to_scene(scene_id, avatar_config)
        self.assertTrue(result)

    async def test_add_avatar_to_nonexistent_scene(self):
        result = await self.mgr.add_avatar_to_scene("nonexistent", {"avatar_id": "av1"})
        self.assertFalse(result)
