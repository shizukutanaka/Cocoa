"""Acceptance tests for cache_manager.py.

Spec: docs/SPEC_CACHE_MANAGER.md (REQ-CM-01..04)
Runnable without pytest:  python3 -m unittest tests.test_cache_manager -v
"""
import asyncio
import sys
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

import tempfile

from cache_manager import (
    CacheManager,
    FileCache,
    MemoryCache,
    async_cached,
    cached,
)


class TestMemoryCache(unittest.TestCase):
    def test_set_and_get(self):
        cache = MemoryCache(max_size=10, ttl_seconds=60)
        cache.set("k", "v")
        self.assertEqual(cache.get("k"), "v")

    def test_get_missing_returns_none(self):
        cache = MemoryCache()
        self.assertIsNone(cache.get("nonexistent"))

    def test_ttl_expiry(self):
        cache = MemoryCache(max_size=10, ttl_seconds=0)
        cache.set("k", "v")
        time.sleep(0.01)
        self.assertIsNone(cache.get("k"))

    def test_lru_eviction(self):
        cache = MemoryCache(max_size=2, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # evicts "a"
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.get("b"), 2)
        self.assertEqual(cache.get("c"), 3)

    def test_delete_existing_key(self):
        cache = MemoryCache()
        cache.set("k", "v")
        cache.delete("k")
        self.assertIsNone(cache.get("k"))

    def test_delete_nonexistent_key_no_error(self):
        cache = MemoryCache()
        cache.delete("ghost")  # must not raise

    def test_delete_keeps_access_order_consistent(self):
        # max_size=2: after delete "a" (size=1), set "c" (size=2),
        # set "d" triggers eviction of oldest="b"
        cache = MemoryCache(max_size=2, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.delete("a")   # size → 1
        cache.set("c", 3)   # size → 2, no eviction
        cache.set("d", 4)   # size=2 >= max → evict "b"
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("c"), 3)
        self.assertEqual(cache.get("d"), 4)

    def test_clear(self):
        cache = MemoryCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        self.assertIsNone(cache.get("a"))
        self.assertIsNone(cache.get("b"))

    def test_overwrite_existing_key(self):
        cache = MemoryCache()
        cache.set("k", "old")
        cache.set("k", "new")
        self.assertEqual(cache.get("k"), "new")

    def test_stats_has_expected_keys(self):
        cache = MemoryCache(max_size=5)
        cache.set("x", 42)
        s = cache.stats()
        self.assertIn("size", s)
        self.assertIn("max_size", s)
        self.assertEqual(s["size"], 1)
        self.assertEqual(s["max_size"], 5)


class TestCacheManagerInvalidate(unittest.TestCase):
    def test_invalidate_removes_from_memory(self):
        cm = CacheManager()
        cm.memory_cache.set("key", "value")
        cm.invalidate("key")
        self.assertIsNone(cm.memory_cache.get("key"))

    def test_invalidate_nonexistent_key_no_error(self):
        cm = CacheManager()
        cm.invalidate("ghost")  # must not raise

    def test_invalidate_keeps_other_keys(self):
        cm = CacheManager()
        cm.memory_cache.set("keep", "yes")
        cm.memory_cache.set("drop", "no")
        cm.invalidate("drop")
        self.assertEqual(cm.memory_cache.get("keep"), "yes")
        self.assertIsNone(cm.memory_cache.get("drop"))


class TestCachedDecorator(unittest.TestCase):
    def setUp(self):
        import cache_manager
        cache_manager._cache_manager = None  # reset global

    def test_wraps_preserves_name(self):
        @cached()
        def my_special_function():
            return 42

        self.assertEqual(my_special_function.__name__, "my_special_function")

    def test_wraps_preserves_doc(self):
        @cached()
        def documented():
            """docstring here"""
            return 1

        self.assertEqual(documented.__doc__, "docstring here")

    def test_returns_correct_result(self):
        @cached()
        def add(a, b):
            return a + b

        self.assertEqual(add(2, 3), 5)

    def test_cached_result_returned_on_second_call(self):
        call_count = [0]

        @cached()
        def expensive():
            call_count[0] += 1
            return "result"

        expensive()
        expensive()
        self.assertEqual(call_count[0], 1)


class TestAsyncCachedDecorator(unittest.TestCase):
    def test_async_cached_is_not_coroutine(self):
        # async_cached() should be callable as a regular decorator, not needing await
        import inspect
        result = async_cached()
        self.assertFalse(inspect.iscoroutine(result), "async_cached() must not return a coroutine")

    def test_async_cached_returns_decorator(self):
        decorator = async_cached()
        self.assertTrue(callable(decorator))

    def test_async_cached_can_decorate_coroutine(self):
        @async_cached()
        async def fetch(x):
            return x * 10

        result = asyncio.run(fetch(3))
        self.assertEqual(result, 30)


class TestFileCache(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cache = FileCache(cache_dir=self.tmpdir, ttl_seconds=60)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_set_and_get(self):
        self.cache.set("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.cache.get("nonexistent"))

    def test_set_complex_value(self):
        data = {"nested": [1, 2, 3], "flag": True}
        self.cache.set("complex", data)
        self.assertEqual(self.cache.get("complex"), data)

    def test_clear_removes_all(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.clear()
        self.assertIsNone(self.cache.get("a"))
        self.assertIsNone(self.cache.get("b"))

    def test_ttl_expiry(self):
        cache = FileCache(cache_dir=self.tmpdir, ttl_seconds=0)
        cache.set("expiring", "val")
        # Immediately after setting with TTL=0, mtime check means already expired
        time.sleep(0.01)
        self.assertIsNone(cache.get("expiring"))

    def test_cleanup_expired_returns_count(self):
        fast_cache = FileCache(cache_dir=self.tmpdir, ttl_seconds=0)
        fast_cache.set("e1", "v1")
        fast_cache.set("e2", "v2")
        time.sleep(0.01)
        count = fast_cache.cleanup_expired()
        self.assertGreaterEqual(count, 2)

    def test_overwrite_key(self):
        self.cache.set("k", "old")
        self.cache.set("k", "new")
        self.assertEqual(self.cache.get("k"), "new")


if __name__ == "__main__":
    unittest.main(verbosity=2)
