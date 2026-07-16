"""Tests for integrated_security module."""
import os
import sys
import tempfile
import unittest

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


class TestUpdateMlModelWithoutSklearn(unittest.TestCase):
    """_update_ml_model() must be a no-op when sklearn is unavailable.

    Bug: method called StandardScaler() / IsolationForest() unconditionally,
    raising NameError when SKLEARN_AVAILABLE=False.
    Fix: early return guarded by SKLEARN_AVAILABLE.
    """

    def _make_anomaly_detector(self):
        from integrated_security import AdvancedBehaviorAnalyzer
        return AdvancedBehaviorAnalyzer()

    def test_update_ml_model_no_crash_without_sklearn(self):
        from unittest.mock import patch
        import integrated_security as isec
        detector = self._make_anomaly_detector()
        # Simulate sklearn being unavailable at runtime
        with patch.object(isec, 'SKLEARN_AVAILABLE', False):
            for i in range(60):
                detector.record_behavior("u1", "login", float(i))
            # Must not raise NameError / AttributeError
            detector._update_ml_model("u1", "login")

    def test_update_ml_model_skips_training_without_sklearn(self):
        from unittest.mock import patch
        import integrated_security as isec
        detector = self._make_anomaly_detector()
        with patch.object(isec, 'SKLEARN_AVAILABLE', False):
            # Pre-populate the behavior buffer with 60 entries
            from collections import deque
            behavior_key = "login_u2"
            detector.user_behaviors[behavior_key] = deque(
                [{"value": float(i), "timestamp": i, "user_id": "u2", "behavior_type": "login"}
                 for i in range(60)],
                maxlen=1000
            )
            # Should return without creating a model
            detector._update_ml_model("u2", "login")
            self.assertNotIn("u2", detector.ml_models)


class TestSignatureComparisonConstantTime(unittest.TestCase):
    """Signature verification must use hmac.compare_digest, not ==.

    Qiita/Zenn anti-pattern: comparing secrets with `==` short-circuits on
    the first differing byte, leaking information through timing. The
    canonical fix is `hmac.compare_digest(a, b)` which always compares the
    full length.

    AST-based check so we don't need the heavy crypto deps at test time.
    """

    def test_no_bare_equality_on_signature_signature(self):
        import ast, pathlib
        src = pathlib.Path("main/integrated_security.py").read_text()
        tree = ast.parse(src)
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            if not (len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq)):
                continue
            left = node.left
            # Look for signature.signature == ... or ... == signature.signature
            for operand in (left, *node.comparators):
                if (isinstance(operand, ast.Attribute)
                        and operand.attr == "signature"
                        and isinstance(operand.value, ast.Name)
                        and operand.value.id == "signature"):
                    offenders.append(node.lineno)
        self.assertEqual(
            offenders, [],
            f"signature.signature must use hmac.compare_digest, not == "
            f"(offending lines: {offenders})"
        )

    def test_hmac_compare_digest_used_for_signature_verification(self):
        import pathlib
        src = pathlib.Path("main/integrated_security.py").read_text()
        # Both fallback verifiers must use compare_digest
        self.assertGreaterEqual(
            src.count("hmac.compare_digest(signature.signature"),
            2,
            "Both _dilithium_verify and _fallback_verify must use hmac.compare_digest",
        )


if __name__ == '__main__':
    unittest.main()
