"""Tests for preset_manager module."""
import sys
import os
import json
import unittest
import tempfile
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


def make_manager(tmpdir):
    from preset_manager import PresetManager
    logger = logging.getLogger("test")
    return PresetManager(logger, preset_dir=tmpdir)


class TestPresetManagerBasic(unittest.TestCase):
    def test_empty_load(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            mgr.load_presets()
            self.assertEqual(mgr.get_all_presets(), {})

    def test_save_and_get(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            mgr.save_preset("p1", {"key": "value", "tags": ["anime"]})
            result = mgr.get_preset("p1")
            self.assertIsNotNone(result)
            self.assertEqual(result["key"], "value")

    def test_get_nonexistent_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            self.assertIsNone(mgr.get_preset("no_such_preset"))

    def test_delete_preset(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            mgr.save_preset("to_delete", {"x": 1})
            mgr.delete_preset("to_delete")
            self.assertIsNone(mgr.get_preset("to_delete"))

    def test_delete_nonexistent_raises(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            from preset_manager import PresetError
            with self.assertRaises(PresetError):
                mgr.delete_preset("phantom")


class TestPresetManagerSearch(unittest.TestCase):
    def test_search_by_tag(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            mgr.save_preset("anime_p", {"tags": ["anime", "cute"]})
            mgr.save_preset("realistic_p", {"tags": ["realistic"]})
            results = mgr.search_presets("anime")
            self.assertIn("anime_p", results)
            self.assertNotIn("realistic_p", results)

    def test_search_empty_query(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            mgr.save_preset("p1", {"tags": ["x"]})
            mgr.save_preset("p2", {"tags": ["y"]})
            results = mgr.search_presets("")
            self.assertGreaterEqual(len(results), 2)


class TestPresetManagerCompare(unittest.TestCase):
    def test_compare_identical(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            data = {"a": 1, "b": 2}
            mgr.save_preset("p1", data)
            mgr.save_preset("p2", data)
            diff = mgr.compare_presets("p1", "p2")
            self.assertIsInstance(diff, dict)

    def test_compare_different(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            mgr.save_preset("p1", {"a": 1})
            mgr.save_preset("p2", {"a": 2})
            diff = mgr.compare_presets("p1", "p2")
            self.assertIsInstance(diff, dict)


class TestBatchOperations(unittest.TestCase):
    def test_batch_update(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            mgr.save_preset("x1", {"v": 1})
            mgr.save_preset("x2", {"v": 2})
            results = mgr.batch_update_presets({"x1": {"v": 10}, "x2": {"v": 20}})
            self.assertTrue(results["x1"])
            self.assertTrue(results["x2"])

    def test_batch_delete(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            mgr.save_preset("d1", {"v": 1})
            mgr.save_preset("d2", {"v": 2})
            results = mgr.batch_delete_presets(["d1", "d2"])
            self.assertTrue(results["d1"])
            self.assertTrue(results["d2"])


if __name__ == '__main__':
    unittest.main()
