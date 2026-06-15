"""Tests for main/idempotency.py"""
import sys
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from idempotency import IdempotencyStore, get_idempotency_store


class TestIdempotencyStore(unittest.TestCase):
    def setUp(self):
        self.store = IdempotencyStore()
        self.calls = []

    def _fn(self, tag="x"):
        def run():
            self.calls.append(tag)
            return {"tag": tag, "n": len(self.calls)}
        return run

    def test_same_key_executes_once(self):
        r1 = self.store.get_or_execute("u:k1", self._fn())
        r2 = self.store.get_or_execute("u:k1", self._fn())
        self.assertEqual(r1, r2)
        self.assertEqual(len(self.calls), 1)

    def test_replay_returns_original_result(self):
        first = self.store.get_or_execute("u:k1", self._fn("first"))
        second = self.store.get_or_execute("u:k1", self._fn("second"))
        # The cached first result is replayed, the second fn never runs.
        self.assertEqual(second["tag"], "first")
        self.assertEqual(self.calls, ["first"])

    def test_different_keys_execute_independently(self):
        self.store.get_or_execute("u:k1", self._fn())
        self.store.get_or_execute("u:k2", self._fn())
        self.assertEqual(len(self.calls), 2)

    def test_empty_key_always_executes(self):
        self.store.get_or_execute("", self._fn())
        self.store.get_or_execute(None, self._fn())
        self.assertEqual(len(self.calls), 2)

    def test_seen(self):
        self.assertFalse(self.store.seen("u:k1"))
        self.store.get_or_execute("u:k1", self._fn())
        self.assertTrue(self.store.seen("u:k1"))

    def test_ttl_expiry_allows_re_execution(self):
        store = IdempotencyStore(ttl_seconds=0)
        store.get_or_execute("u:k1", self._fn())
        time.sleep(0.01)
        store.get_or_execute("u:k1", self._fn())
        self.assertEqual(len(self.calls), 2)  # expired → re-executed

    def test_max_entries_eviction_bounds_size(self):
        store = IdempotencyStore(max_entries=5)
        for i in range(20):
            store.get_or_execute(f"k{i}", lambda: 1)
        self.assertLessEqual(store.size(), 5)

    def test_concurrent_same_key_executes_once(self):
        store = IdempotencyStore()
        n = 32
        barrier = threading.Barrier(n)
        exec_count = []
        lock = threading.Lock()

        def fn():
            with lock:
                exec_count.append(1)
            return {"v": 42}

        results = []

        def worker():
            barrier.wait()
            r = store.get_or_execute("u:same", fn)
            with lock:
                results.append(r)

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(exec_count), 1)             # executed exactly once
        self.assertTrue(all(r == {"v": 42} for r in results))  # all got same result

    def test_singleton(self):
        self.assertIs(get_idempotency_store(), get_idempotency_store())


if __name__ == "__main__":
    unittest.main(verbosity=2)
