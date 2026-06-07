"""Acceptance tests for redis_cache_manager.py (FallbackCacheManager path).

Spec: docs/SPEC_REDIS_CACHE_MANAGER.md (REQ-RCM-01..04)
Runnable without pytest:  python3 -m unittest tests.test_redis_cache_manager -v

All tests exercise FallbackCacheManager because redis is not installed in the
test environment. RedisCacheManager itself is tested only at the import level.
"""
import asyncio
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

import redis_cache_manager as rcm  # noqa: E402
from redis_cache_manager import FallbackCacheManager, get_cache_manager  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


class TestFallbackCacheManagerBasics(unittest.TestCase):
    def setUp(self):
        self.cm = FallbackCacheManager()

    def test_constructor_does_not_raise(self):
        self.assertIsNotNone(self.cm)

    def test_get_nonexistent_returns_none(self):
        result = _run(self.cm.get("no_such_key"))
        self.assertIsNone(result)

    def test_set_then_get_returns_value(self):
        _run(self.cm.set("mykey", {"data": 42}))
        result = _run(self.cm.get("mykey"))
        self.assertIsNotNone(result)
        self.assertEqual(result["data"], 42)

    def test_set_returns_true(self):
        ok = _run(self.cm.set("k", "v"))
        self.assertTrue(ok)

    def test_set_scalar_value(self):
        _run(self.cm.set("num", 99))
        result = _run(self.cm.get("num"))
        self.assertEqual(result, 99)

    def test_overwrite_key(self):
        _run(self.cm.set("x", 1))
        _run(self.cm.set("x", 2))
        result = _run(self.cm.get("x"))
        self.assertEqual(result, 2)


class TestFallbackCacheManagerDelete(unittest.TestCase):
    def setUp(self):
        self.cm = FallbackCacheManager()

    def test_delete_returns_true(self):
        _run(self.cm.set("del_key", "val"))
        result = _run(self.cm.delete("del_key"))
        self.assertTrue(result)

    def test_delete_removes_value(self):
        _run(self.cm.set("gone", "bye"))
        _run(self.cm.delete("gone"))
        result = _run(self.cm.get("gone"))
        self.assertIsNone(result)

    def test_delete_nonexistent_does_not_raise(self):
        result = _run(self.cm.delete("not_there"))
        self.assertTrue(result)


class TestFallbackCacheManagerExists(unittest.TestCase):
    def setUp(self):
        self.cm = FallbackCacheManager()

    def test_exists_false_for_new_key(self):
        result = _run(self.cm.exists("fresh_key"))
        self.assertFalse(result)

    def test_exists_true_after_set(self):
        _run(self.cm.set("present", True))
        result = _run(self.cm.exists("present"))
        self.assertTrue(result)

    def test_exists_false_after_delete(self):
        _run(self.cm.set("temp", "v"))
        _run(self.cm.delete("temp"))
        result = _run(self.cm.exists("temp"))
        self.assertFalse(result)


class TestFallbackCacheManagerStats(unittest.TestCase):
    def test_get_stats_returns_dict(self):
        cm = FallbackCacheManager()
        stats = _run(cm.get_stats())
        self.assertIsInstance(stats, dict)
        self.assertIn("cache_type", stats)


class TestFallbackCachedAsyncDecorator(unittest.TestCase):
    def test_cached_async_returns_callable(self):
        cm = FallbackCacheManager()
        decorator = cm.cached_async(ttl=60)
        self.assertTrue(callable(decorator))

    def test_cached_async_decorated_function_callable(self):
        cm = FallbackCacheManager()

        @cm.cached_async(ttl=60)
        async def my_func(x):
            return x * 2

        self.assertTrue(callable(my_func))

    def test_cached_async_returns_result(self):
        cm = FallbackCacheManager()

        @cm.cached_async()
        async def compute(n):
            return n + 1

        result = _run(compute(5))
        self.assertEqual(result, 6)

    def test_cached_async_caches_result(self):
        cm = FallbackCacheManager()
        call_count = [0]

        @cm.cached_async()
        async def expensive(n):
            call_count[0] += 1
            return n * 10

        _run(expensive(3))
        _run(expensive(3))
        self.assertEqual(call_count[0], 1)

    def test_cached_async_preserves_function_name(self):
        cm = FallbackCacheManager()

        @cm.cached_async()
        async def named_func():
            return 1

        self.assertEqual(named_func.__name__, "named_func")


class TestFallbackCachedSyncDecorator(unittest.TestCase):
    def test_cached_sync_returns_callable(self):
        cm = FallbackCacheManager()
        decorator = cm.cached_sync(ttl=60)
        self.assertTrue(callable(decorator))

    def test_cached_sync_decorated_function_callable(self):
        cm = FallbackCacheManager()

        @cm.cached_sync(ttl=60)
        def my_func(x):
            return x * 2

        self.assertTrue(callable(my_func))

    def test_cached_sync_returns_result(self):
        cm = FallbackCacheManager()

        @cm.cached_sync()
        def double(n):
            return n * 2

        self.assertEqual(double(4), 8)

    def test_cached_sync_caches_result(self):
        cm = FallbackCacheManager()
        call_count = [0]

        @cm.cached_sync()
        def heavy(n):
            call_count[0] += 1
            return n + 100

        heavy(7)
        heavy(7)
        self.assertEqual(call_count[0], 1)

    def test_cached_sync_preserves_function_name(self):
        cm = FallbackCacheManager()

        @cm.cached_sync()
        def sync_named():
            return 0

        self.assertEqual(sync_named.__name__, "sync_named")


class TestGetCacheManager(unittest.TestCase):
    def setUp(self):
        rcm._cache_manager = None

    def test_returns_manager_instance(self):
        manager = get_cache_manager()
        self.assertIsNotNone(manager)

    def test_returns_fallback_when_redis_unavailable(self):
        manager = get_cache_manager()
        self.assertIsInstance(manager, FallbackCacheManager)

    def test_singleton_same_instance(self):
        m1 = get_cache_manager()
        m2 = get_cache_manager()
        self.assertIs(m1, m2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
