"""Acceptance tests for redis_cache_manager.py (FallbackCacheManager path).

Spec: docs/SPEC_REDIS_CACHE_MANAGER.md (REQ-RCM-01..04)
Runnable without pytest:  python3 -m unittest tests.test_redis_cache_manager -v

All tests exercise FallbackCacheManager because redis is not installed in the
test environment. RedisCacheManager itself is tested only at the import level.
"""
import asyncio
import os
import pickle
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

import redis_cache_manager as rcm
from redis_cache_manager import FallbackCacheManager, get_cache_manager


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


class TestRedisCacheManagerTtlCheck(unittest.TestCase):
    """RedisCacheManager.get() must correctly interpret Redis TTL return codes.

    Bug: the code checked `if ttl == -1` (key exists without expiry) and
    treated it as a cache miss, so any key stored without a TTL was silently
    invisible.  Redis semantics: -1 = key has no expiry (still a valid hit),
    -2 = key does not exist.
    Fix: check `if ttl == -2` instead.
    """

    def _make_redis_mgr(self):
        """Build a RedisCacheManager with a mocked async redis client."""
        from unittest.mock import AsyncMock, MagicMock, patch
        from redis_cache_manager import RedisCacheManager
        with patch.object(RedisCacheManager, '__init__', lambda self: None):
            mgr = RedisCacheManager.__new__(RedisCacheManager)
        mgr.is_healthy = True
        mgr.lock = __import__('threading').Lock()
        mgr.stats = {'hits': 0, 'misses': 0, 'errors': 0}
        mgr.redis_async_client = AsyncMock()
        return mgr

    def test_ttl_minus_2_returns_none(self):
        """ttl==-2 means key was deleted; must be a miss."""
        import asyncio
        from unittest.mock import AsyncMock
        mgr = self._make_redis_mgr()
        mgr.redis_async_client.get = AsyncMock(return_value=b"some_value")
        mgr.redis_async_client.ttl = AsyncMock(return_value=-2)
        result = asyncio.run(mgr.get("test_key"))
        self.assertIsNone(result)

    def test_ttl_minus_1_is_a_cache_hit(self):
        """ttl==-1 means key exists without expiry; must be a hit, not a miss."""
        import asyncio
        import json
        from unittest.mock import AsyncMock
        mgr = self._make_redis_mgr()
        # Use the canonical JSON serialization (raw unsigned pickle is now
        # refused on read for security — see TestSignedPickleDeserialization).
        payload = json.dumps({"answer": 42})
        mgr.redis_async_client.get = AsyncMock(return_value=payload)
        mgr.redis_async_client.ttl = AsyncMock(return_value=-1)
        result = asyncio.run(mgr.get("persistent_key"))
        self.assertIsNotNone(result, "Key with no-expiry (ttl==-1) must return cached value, not None")
        self.assertEqual(result["answer"], 42)


class TestRedisCachedSyncNoLeakedTasks(unittest.TestCase):
    """RedisCacheManager.cached_sync() must not create orphaned asyncio tasks.

    Bug: when the event loop was already running, the decorator created tasks
    via loop.create_task() then immediately called loop.run_until_complete(),
    which raised RuntimeError.  The created tasks were orphaned (never awaited,
    never cancelled) and leaked.
    Fix: skip cache I/O entirely when the loop is already running instead of
    creating tasks that can't be resolved.
    """

    def test_cached_sync_does_not_raise_inside_running_loop(self):
        """cached_sync function must return the correct value from an async context."""
        from unittest.mock import AsyncMock, MagicMock, patch
        from redis_cache_manager import RedisCacheManager

        with patch.object(RedisCacheManager, '__init__', lambda self: None):
            mgr = RedisCacheManager.__new__(RedisCacheManager)
        mgr.is_healthy = True
        mgr.lock = __import__('threading').Lock()
        mgr.stats = {'hits': 0, 'misses': 0, 'errors': 0}
        mgr.redis_async_client = AsyncMock()
        mgr.redis_async_client.get = AsyncMock(return_value=None)
        mgr.redis_async_client.set = AsyncMock(return_value=True)

        call_count = [0]

        @mgr.cached_sync(ttl=60)
        def compute(n):
            call_count[0] += 1
            return n * 2

        async def run_inside_loop():
            result = compute(5)
            return result

        result = asyncio.run(run_inside_loop())
        self.assertEqual(result, 10)
        self.assertEqual(call_count[0], 1)


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


# Module-level flag a malicious pickle would flip if pickle.loads() ran it.
_rce_canary = {"fired": False}


def _trip_canary():
    _rce_canary["fired"] = True
    return "pwned"


class _EvilPayload:
    """When unpickled, calls _trip_canary() — simulates an RCE gadget."""
    def __reduce__(self):
        return (_trip_canary, ())


class TestSignedPickleDeserialization(unittest.TestCase):
    """RedisCacheManager must never pickle.loads() untrusted/forged cache data.

    pickle.loads() executes arbitrary code via __reduce__, so a poisoned Redis
    value (the 'untrusted cache source' Qiita flags) is an RCE vector. The fix
    HMAC-signs pickle payloads: only data Cocoa itself serialized (with the
    secret) is ever unpickled. With no key configured, pickle is disabled
    entirely (fail closed).
    """

    def _mgr(self):
        # Bypass __init__ (which needs redis); only serializer state is needed.
        mgr = rcm.RedisCacheManager.__new__(rcm.RedisCacheManager)
        mgr.compression_threshold = 1 << 30
        return mgr

    def setUp(self):
        self._saved = os.environ.get("COCOA_CACHE_HMAC_KEY")
        _rce_canary["fired"] = False

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("COCOA_CACHE_HMAC_KEY", None)
        else:
            os.environ["COCOA_CACHE_HMAC_KEY"] = self._saved
        _rce_canary["fired"] = False

    def test_json_value_roundtrips_without_key(self):
        os.environ.pop("COCOA_CACHE_HMAC_KEY", None)
        mgr = self._mgr()
        s = mgr._serialize_value({"a": 1, "b": [1, 2, 3]})
        self.assertEqual(mgr._deserialize_value(s), {"a": 1, "b": [1, 2, 3]})

    def test_non_json_value_roundtrips_with_key(self):
        os.environ["COCOA_CACHE_HMAC_KEY"] = "unit-test-secret"
        mgr = self._mgr()
        # dict with a tuple key is NOT JSON-serializable even with default=str.
        value = {(1, 2): "x", (3, 4): "y"}
        s = mgr._serialize_value(value)
        self.assertTrue(s.startswith(rcm.RedisCacheManager._PICKLE_MARKER))
        self.assertEqual(mgr._deserialize_value(s), value)

    def test_non_json_value_refused_without_key(self):
        os.environ.pop("COCOA_CACHE_HMAC_KEY", None)
        mgr = self._mgr()
        with self.assertRaises(ValueError):
            mgr._serialize_value({(1, 2): "x"})  # would need pickle, but no key

    def test_forged_pickle_is_not_unpickled(self):
        """A poisoned value carrying our marker but a bad HMAC must NOT run."""
        os.environ["COCOA_CACHE_HMAC_KEY"] = "the-real-secret"
        mgr = self._mgr()
        # Attacker builds an RCE pickle and guesses the wire format, but cannot
        # forge the HMAC without the secret.
        evil_raw = pickle.dumps(_EvilPayload())
        forged = (rcm.RedisCacheManager._PICKLE_MARKER
                  + "deadbeef" * 8 + ":" + evil_raw.decode("latin1"))
        with self.assertRaises(ValueError):
            mgr._deserialize_value(forged)
        self.assertFalse(_rce_canary["fired"],
                         "pickle.loads must NOT run on a payload with an invalid HMAC")

    def test_forged_pickle_refused_when_key_unset(self):
        os.environ.pop("COCOA_CACHE_HMAC_KEY", None)
        mgr = self._mgr()
        evil_raw = pickle.dumps(_EvilPayload())
        forged = (rcm.RedisCacheManager._PICKLE_MARKER
                  + "00" + ":" + evil_raw.decode("latin1"))
        with self.assertRaises(ValueError):
            mgr._deserialize_value(forged)
        self.assertFalse(_rce_canary["fired"])

    def test_validly_signed_pickle_does_run(self):
        """Sanity: the legitimate self-signed path still works end to end."""
        os.environ["COCOA_CACHE_HMAC_KEY"] = "the-real-secret"
        mgr = self._mgr()
        # Nest the gadget under a tuple key so json.dumps fails and the pickle
        # path is taken; we sign it ourselves so it is trusted on the way back.
        signed = mgr._serialize_value({(0,): _EvilPayload()})
        self.assertTrue(signed.startswith(rcm.RedisCacheManager._PICKLE_MARKER))
        mgr._deserialize_value(signed)
        # Our own signed payload is trusted, so __reduce__ runs on read-back.
        self.assertTrue(_rce_canary["fired"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
