"""Tests for integrated_security module."""
import sys
import os
import unittest
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestThreatLevel(unittest.TestCase):
    def test_values(self):
        from integrated_security import ThreatLevel
        self.assertIsNotNone(ThreatLevel.LOW)
        self.assertIsNotNone(ThreatLevel.HIGH)
        self.assertIsNotNone(ThreatLevel.CRITICAL)


class TestSecurityLevel(unittest.TestCase):
    def test_values(self):
        from integrated_security import SecurityLevel
        levels = list(SecurityLevel)
        self.assertGreater(len(levels), 0)


class TestSecurityPolicy(unittest.TestCase):
    def test_defaults(self):
        from integrated_security import SecurityPolicy
        policy = SecurityPolicy()
        self.assertIsInstance(policy.max_login_attempts, int)
        self.assertIsInstance(policy.session_timeout, int)

    def test_custom(self):
        from integrated_security import SecurityPolicy
        policy = SecurityPolicy(max_login_attempts=3)
        self.assertEqual(policy.max_login_attempts, 3)


class TestSecurityEvent(unittest.TestCase):
    def test_creation(self):
        from integrated_security import SecurityEvent
        event = SecurityEvent(
            event_type="login",
            user_id="user_1",
            resource="auth",
            details={},
        )
        self.assertEqual(event.event_type, "login")
        self.assertIsNotNone(event.timestamp)

    def test_timestamp_set(self):
        from integrated_security import SecurityEvent
        event = SecurityEvent(event_type="test", user_id="u", resource="r", details={})
        self.assertIsNotNone(event.timestamp)
        self.assertIsInstance(event.timestamp, float)


class TestPrivacyProtector(unittest.TestCase):
    def test_anonymize_data(self):
        from integrated_security import PrivacyProtector
        pp = PrivacyProtector()
        pp.add_privacy_policy("u1", {"anonymize_fields": ["name"], "allowed_sharing": []})
        result = pp.anonymize_data({"name": "Alice", "age": 30}, "u1")
        self.assertIsInstance(result, dict)
        self.assertNotEqual(result.get("name"), "Alice")

    def test_anonymize_no_policy(self):
        from integrated_security import PrivacyProtector
        pp = PrivacyProtector()
        data = {"name": "Alice"}
        result = pp.anonymize_data(data, "unknown_user")
        self.assertEqual(result, data)

    def test_check_data_sharing_allowed(self):
        from integrated_security import PrivacyProtector
        pp = PrivacyProtector()
        pp.add_privacy_policy("u1", {"allowed_sharing": ["partner1"]})
        self.assertTrue(pp.check_data_sharing("u1", "partner1"))
        self.assertFalse(pp.check_data_sharing("u1", "unknown"))


class TestSecurityAuditor(unittest.TestCase):
    def _make(self, tmpdir):
        from integrated_security import SecurityAuditor
        db_path = os.path.join(tmpdir, "security.db")
        return SecurityAuditor(db_path=db_path)

    def test_init_database(self):
        with tempfile.TemporaryDirectory() as d:
            auditor = self._make(d)
            self.assertTrue(os.path.exists(auditor.db_path))

    def test_log_event(self):
        from integrated_security import SecurityEvent
        with tempfile.TemporaryDirectory() as d:
            auditor = self._make(d)
            event = SecurityEvent(
                event_type="test_event",
                user_id="u1",
                resource="resource1",
                details={"action": "test"},
            )
            auditor.log_event(event)

    def test_get_events(self):
        from integrated_security import SecurityEvent
        with tempfile.TemporaryDirectory() as d:
            auditor = self._make(d)
            event = SecurityEvent(
                event_type="test_event",
                user_id="u1",
                resource="r",
                details={},
            )
            auditor.log_event(event)
            events = auditor.get_events(hours_back=24)
            self.assertIsInstance(events, list)
            self.assertGreater(len(events), 0)


class TestSecurityValidator(unittest.TestCase):
    def _make(self):
        from integrated_security import SecurityValidator
        return SecurityValidator()

    def test_validate_password_strong(self):
        v = self._make()
        valid, msg = v.validate_password("StrongP@ss1!")
        self.assertTrue(valid)

    def test_validate_weak_password(self):
        v = self._make()
        valid, msg = v.validate_password("123")
        self.assertFalse(valid)

    def test_validate_input_data_clean(self):
        v = self._make()
        valid, msg = v.validate_input_data({"name": "hello"})
        self.assertTrue(valid)

    def test_validate_input_data_xss(self):
        v = self._make()
        valid, msg = v.validate_input_data("<script>alert('xss')</script>")
        self.assertFalse(valid)

    def test_sanitize_input(self):
        v = self._make()
        result = v.sanitize_input("<script>alert('xss')</script>")
        self.assertNotIn("<script>", result)

    def test_validate_user_access_no_restrictions(self):
        v = self._make()
        ok, msg = v.validate_user_access("user1", "resource1")
        self.assertTrue(ok)


if __name__ == '__main__':
    unittest.main()
