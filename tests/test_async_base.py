"""Acceptance tests for async_base.py improvements.

Spec: docs/SPEC_ASYNC_BASE.md (REQ-AB-01..04)
Runnable without pytest:  python3 -m unittest tests.test_async_base -v
"""
import asyncio
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from async_base import (
    AsyncBatch,
    AsyncCache,
    async_timeout,
    process_stream,
)


def run(coro):
    return asyncio.run(coro)


class TestAsyncBatch(unittest.TestCase):
    def test_processes_all_items(self):
        async def double(x):
            return x * 2

        batch = AsyncBatch(batch_size=3, timeout=5.0)
        results = run(batch.process([1, 2, 3, 4, 5], double))
        self.assertEqual(sorted(results), [2, 4, 6, 8, 10])

    def test_handles_individual_exception_in_batch(self):
        async def maybe_fail(x):
            if x == 3:
                raise ValueError("bad value")
            return x

        batch = AsyncBatch(batch_size=10, timeout=5.0)
        results = run(batch.process([1, 2, 3, 4], maybe_fail))
        # x=3 produces an exception; others succeed
        self.assertIn(1, results)
        self.assertIn(2, results)
        self.assertIn(4, results)
        self.assertNotIn(3, results)

    def test_timeout_raises(self):
        async def slow(_):
            await asyncio.sleep(10)  # longer than timeout

        batch = AsyncBatch(batch_size=10, timeout=0.05)  # 50ms
        with self.assertRaises(asyncio.TimeoutError):
            run(batch.process([1], slow))

    def test_empty_items_returns_empty(self):
        async def identity(x):
            return x

        batch = AsyncBatch(batch_size=5, timeout=5.0)
        results = run(batch.process([], identity))
        self.assertEqual(results, [])

    def test_batch_size_chunking(self):
        processed = []

        async def record(x):
            processed.append(x)
            return x

        batch = AsyncBatch(batch_size=2, timeout=5.0)
        run(batch.process([1, 2, 3, 4, 5], record))
        self.assertEqual(sorted(processed), [1, 2, 3, 4, 5])


class TestAsyncCache(unittest.TestCase):
    def test_set_and_get(self):
        cache = AsyncCache(ttl=60.0)
        run(cache.set("key", "value"))
        result = run(cache.get("key"))
        self.assertEqual(result, "value")

    def test_get_missing_key_returns_none(self):
        cache = AsyncCache(ttl=60.0)
        result = run(cache.get("nonexistent"))
        self.assertIsNone(result)

    def test_expired_key_returns_none(self):
        cache = AsyncCache(ttl=0.01)  # 10ms TTL
        run(cache.set("key", "value"))
        import time
        time.sleep(0.02)  # let it expire
        result = run(cache.get("key"))
        self.assertIsNone(result)

    def test_zero_ttl_is_persistent(self):
        # REQ-AB-03: ttl=0 means no expiry
        cache = AsyncCache(ttl=0)
        run(cache.set("key", "persistent"))
        result = run(cache.get("key"))
        self.assertEqual(result, "persistent")

    def test_negative_ttl_is_persistent(self):
        cache = AsyncCache(ttl=-1)
        run(cache.set("key", "value"))
        result = run(cache.get("key"))
        self.assertEqual(result, "value")

    def test_delete(self):
        cache = AsyncCache(ttl=60.0)
        run(cache.set("key", "value"))
        run(cache.delete("key"))
        result = run(cache.get("key"))
        self.assertIsNone(result)

    def test_clear(self):
        cache = AsyncCache(ttl=60.0)
        run(cache.set("a", 1))
        run(cache.set("b", 2))
        run(cache.clear())
        self.assertIsNone(run(cache.get("a")))
        self.assertIsNone(run(cache.get("b")))

    def test_overwrite(self):
        cache = AsyncCache(ttl=60.0)
        run(cache.set("key", "v1"))
        run(cache.set("key", "v2"))
        self.assertEqual(run(cache.get("key")), "v2")


class TestAsyncTimeout(unittest.TestCase):

    def test_completes_within_timeout(self):
        @async_timeout(1.0)
        async def fast():
            return 42

        self.assertEqual(run(fast()), 42)

    def test_raises_on_timeout(self):
        @async_timeout(0.05)
        async def slow():
            await asyncio.sleep(10)

        with self.assertRaises(asyncio.TimeoutError):
            run(slow())

    def test_preserves_function_name(self):
        @async_timeout(1.0)
        async def my_func():
            return 1

        self.assertEqual(my_func.__name__, "my_func")

    def test_passes_args(self):
        @async_timeout(1.0)
        async def add(a, b):
            return a + b

        self.assertEqual(run(add(3, 4)), 7)


class TestProcessStream(unittest.TestCase):

    def test_processes_all_items(self):
        results = []

        async def collector(item):
            results.append(item)

        async def stream():
            for i in range(5):
                yield i

        run(process_stream(stream(), collector, max_concurrent=3))
        self.assertEqual(sorted(results), [0, 1, 2, 3, 4])

    def test_empty_stream(self):
        calls = []

        async def noop(item):
            calls.append(item)

        async def empty():
            return
            yield  # make it an async generator

        run(process_stream(empty(), noop))
        self.assertEqual(calls, [])

    def test_processor_exception_does_not_crash(self):
        async def bad_processor(item):
            raise ValueError("intentional")

        async def stream():
            for i in range(3):
                yield i

        run(process_stream(stream(), bad_processor))  # should not raise


if __name__ == "__main__":
    unittest.main(verbosity=2)
