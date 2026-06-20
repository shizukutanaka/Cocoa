"""Tests for preset_manager module."""
import logging
import os
import sys
import tempfile
import unittest

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


class TestPresetManagerPathTraversal(unittest.TestCase):
    def test_save_path_traversal_raises(self):
        from preset_manager import PresetError
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            with self.assertRaises(PresetError):
                mgr.save_preset("../evil", {"key": "val"})

    def test_delete_path_traversal_raises(self):
        from preset_manager import PresetError
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            with self.assertRaises(PresetError):
                mgr.delete_preset("../../etc/passwd")

    def test_nested_traversal_raises(self):
        from preset_manager import PresetError
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            with self.assertRaises(PresetError):
                mgr.save_preset("subdir/../../escape", {"x": 1})


class TestPresetIndexStaleness(unittest.TestCase):
    def test_resave_clears_old_tag_from_index(self):
        """Updating a preset with different tags must remove the old tags from
        the search index — stale entries cause false positives in search."""
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            mgr.save_preset("p1", {"tags": ["old_tag"]})
            self.assertIn("p1", mgr.search_presets("old_tag"))
            # Re-save with a completely different tag set
            mgr.save_preset("p1", {"tags": ["new_tag"]})
            self.assertNotIn("p1", mgr.search_presets("old_tag"))
            self.assertIn("p1", mgr.search_presets("new_tag"))

    def test_resave_clears_old_param_from_index(self):
        """Updating a preset with different parameters must not leave old
        parameter names as search hits."""
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            mgr.save_preset("p1", {"parameters": {"blue_eyes": 0.5}, "tags": []})
            self.assertIn("p1", mgr.search_presets("blue_eyes"))
            mgr.save_preset("p1", {"parameters": {"red_eyes": 0.5}, "tags": []})
            self.assertNotIn("p1", mgr.search_presets("blue_eyes"))
            self.assertIn("p1", mgr.search_presets("red_eyes"))


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


class TestPresetTagsNonList(unittest.TestCase):
    """_update_index() and _remove_from_index() must not crash when 'tags' is not a list.

    Bug: preset JSON files may have "tags": "string" or "tags": null instead of
    a list.  Iterating directly over a string would index individual characters;
    iterating over None would raise TypeError.
    Fix: guard with `if not isinstance(tags, list): tags = []` in both methods.
    """

    def test_save_preset_with_string_tags_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            # tags is a string instead of a list
            mgr.save_preset("bad_tags", {"name": "test", "tags": "should_be_list"})
            # Should be searchable by name at minimum
            results = mgr.search_presets("bad_tags")
            self.assertIn("bad_tags", results)

    def test_save_preset_with_none_tags_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            mgr.save_preset("null_tags", {"name": "test", "tags": None})
            results = mgr.search_presets("null_tags")
            self.assertIn("null_tags", results)

    def test_delete_preset_with_string_tags_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = make_manager(d)
            mgr.save_preset("bad_tags2", {"name": "test", "tags": "string_not_list"})
            # Delete should not crash when removing from tags index
            mgr.delete_preset("bad_tags2")
            self.assertIsNone(mgr.get_preset("bad_tags2"))


if __name__ == '__main__':
    unittest.main()
