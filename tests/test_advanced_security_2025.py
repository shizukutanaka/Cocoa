"""Tests for advanced_security_2025 module."""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestZeroTrustContext(unittest.TestCase):
    def test_creation(self):
        from advanced_security_2025 import ZeroTrustContext
        ctx = ZeroTrustContext(
            user_id="u1",
            session_id="sess_1",
            device_fingerprint="fp123",
            network_info={"ip": "192.168.1.1"},
            behavioral_pattern={"typing_speed": 60},
            risk_score=0.2,
            access_level="standard",
            compliance_flags=["GDPR"],
        )
        self.assertEqual(ctx.user_id, "u1")
        self.assertAlmostEqual(ctx.risk_score, 0.2)


class TestPostQuantumKeyPair(unittest.TestCase):
    def test_creation(self):
        from advanced_security_2025 import PostQuantumKeyPair
        kp = PostQuantumKeyPair(
            public_key=b"public",
            private_key=b"private",
            algorithm="CRYSTALS-Kyber",
            key_id="key_1",
            created_at="2026-01-01T00:00:00Z",
        )
        self.assertEqual(kp.algorithm, "CRYSTALS-Kyber")


class TestAdvancedSecurityManagerInit(unittest.TestCase):
    def _make(self):
        with patch('advanced_security_2025.get_security_manager', return_value=MagicMock()):
            from advanced_security_2025 import AdvancedSecurityManager
            return AdvancedSecurityManager()

    def test_init(self):
        mgr = self._make()
        self.assertIsNotNone(mgr)

    def test_zero_trust_attribute(self):
        mgr = self._make()
        self.assertIsInstance(mgr.zero_trust_enabled, bool)

    def test_security_events_empty(self):
        mgr = self._make()
        if hasattr(mgr, 'security_events'):
            self.assertIsInstance(mgr.security_events, list)

    def test_get_advanced_security_manager_factory(self):
        import inspect
        from advanced_security_2025 import get_advanced_security_manager
        self.assertTrue(callable(get_advanced_security_manager))


if __name__ == '__main__':
    unittest.main()
