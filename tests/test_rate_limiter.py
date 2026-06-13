"""Tests for main/rate_limiter.py"""
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from rate_limiter import (
    RateLimiter,
    _SlidingWindow,
    add_endpoint_limit,
    get_rate_limiter,
)


class TestSlidingWindow(unittest.TestCase):
    def test_allows_under_limit(self):
        w = _SlidingWindow(5, 60)
        for _ in range(5):
            allowed, remaining, retry_after = w.is_allowed()
            self.assertTrue(allowed)
        self.assertGreaterEqual(remaining, 0)

    def test_blocks_over_limit(self):
        w = _SlidingWindow(3, 60)
        for _ in range(3):
            w.is_allowed()
        allowed, remaining, retry_after = w.is_allowed()
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)
        self.assertGreater(retry_after, 0)

    def test_reset_clears_history(self):
        w = _SlidingWindow(2, 60)
        for _ in range(2):
            w.is_allowed()
        self.assertFalse(w.is_allowed()[0])
        w.reset()
        self.assertTrue(w.is_allowed()[0])

    def test_window_expiry(self):
        w = _SlidingWindow(1, 1)  # 1 second window
        w.is_allowed()
        self.assertFalse(w.is_allowed()[0])
        time.sleep(1.1)
        self.assertTrue(w.is_allowed()[0])


class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        self.limiter = RateLimiter()

    def test_allows_normal_traffic(self):
        for i in range(5):
            allowed, headers = self.limiter.check(f"ip-{i}", "/test", max_requests=10)
            self.assertTrue(allowed)
            self.assertIn("X-RateLimit-Limit", headers)
            self.assertIn("X-RateLimit-Remaining", headers)

    def test_blocks_after_limit(self):
        for _ in range(10):
            self.limiter.check("flood-ip", "/test", max_requests=10)
        allowed, headers = self.limiter.check("flood-ip", "/test", max_requests=10)
        self.assertFalse(allowed)
        self.assertIn("Retry-After", headers)

    def test_different_clients_independent(self):
        for _ in range(10):
            self.limiter.check("client-a", "/test", max_requests=10)
        # client-a is blocked
        allowed_a, _ = self.limiter.check("client-a", "/test", max_requests=10)
        self.assertFalse(allowed_a)
        # client-b is still fine
        allowed_b, _ = self.limiter.check("client-b", "/test", max_requests=10)
        self.assertTrue(allowed_b)

    def test_different_endpoints_independent(self):
        for _ in range(5):
            self.limiter.check("user-1", "/endpoint-a", max_requests=5)
        allowed_a, _ = self.limiter.check("user-1", "/endpoint-a", max_requests=5)
        self.assertFalse(allowed_a)
        allowed_b, _ = self.limiter.check("user-1", "/endpoint-b", max_requests=5)
        self.assertTrue(allowed_b)

    def test_reset_client_unblocks(self):
        for _ in range(10):
            self.limiter.check("reset-me", "/test", max_requests=10)
        blocked, _ = self.limiter.check("reset-me", "/test", max_requests=10)
        self.assertFalse(blocked)
        self.limiter.reset_client("reset-me")
        allowed, _ = self.limiter.check("reset-me", "/test", max_requests=10)
        self.assertTrue(allowed)

    def test_headers_always_present(self):
        _, headers = self.limiter.check("any", "/api")
        for key in ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"):
            self.assertIn(key, headers)

    def test_get_stats(self):
        self.limiter.check("stat-ip", "/path")
        stats = self.limiter.get_stats()
        self.assertIn("active_windows", stats)
        self.assertIn("default_limit", stats)
        self.assertGreater(stats["active_windows"], 0)

    def test_add_endpoint_limit(self):
        add_endpoint_limit("/custom/path", 3, 60)
        for _ in range(3):
            ok, _ = self.limiter.check("ip-1", "/custom/path")
            self.assertTrue(ok)
        ok, _ = self.limiter.check("ip-1", "/custom/path")
        self.assertFalse(ok)

    def test_singleton(self):
        lim1 = get_rate_limiter()
        lim2 = get_rate_limiter()
        self.assertIs(lim1, lim2)

    def test_financial_endpoints_use_strict_limit(self):
        # gift-card lookup/redeem/purchase and refunds must NOT get the
        # generous default rate (enumeration / brute-force / spam protection).
        from rate_limiter import _AUTH_RATE, _DEFAULT_RATE, _ENDPOINT_OVERRIDES
        self.assertGreater(_DEFAULT_RATE, _AUTH_RATE)  # premise: default is looser
        for path in ("/api/gift-cards/lookup", "/api/gift-cards/redeem",
                     "/api/gift-cards", "/api/refunds"):
            self.assertIn(path, _ENDPOINT_OVERRIDES)
            self.assertEqual(_ENDPOINT_OVERRIDES[path].max_requests, _AUTH_RATE)

    def test_gift_card_lookup_blocks_after_strict_limit(self):
        from rate_limiter import _AUTH_RATE
        path = "/api/gift-cards/lookup"
        for _ in range(_AUTH_RATE):
            ok, _ = self.limiter.check("ip-x", path)
            self.assertTrue(ok)
        ok, _ = self.limiter.check("ip-x", path)
        self.assertFalse(ok)  # blocked at the auth-tier limit, not 60


class TestClientIpExtraction(unittest.TestCase):
    def test_extract_forwarded_for(self):
        from rate_limiter import get_client_ip

        class FakeRequest:
            headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
            client = None

        self.assertEqual(get_client_ip(FakeRequest()), "1.2.3.4")

    def test_extract_client_host(self):
        from rate_limiter import get_client_ip

        class FakeClient:
            host = "192.168.1.1"

        class FakeRequest:
            headers = {}
            client = FakeClient()

        self.assertEqual(get_client_ip(FakeRequest()), "192.168.1.1")

    def test_unknown_fallback(self):
        from rate_limiter import get_client_ip

        class FakeRequest:
            headers = {}
            client = None

        self.assertEqual(get_client_ip(FakeRequest()), "unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
