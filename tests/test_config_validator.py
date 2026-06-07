"""Acceptance tests for config_validator.py.

Spec: docs/SPEC_CONFIG_VALIDATOR.md (REQ-CV-01..02)
Runnable without pytest:  python3 -m unittest tests.test_config_validator -v

Uses validate_from_dict() — no file I/O required.
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from config_validator import ConfigValidator  # noqa: E402


def _minimal_valid_config(**overrides):
    cfg = {
        "app_name": "TestApp",
        "version": "1.0.0",
        "language": "ja",
        "debug": False,
        "log_level": "INFO",
    }
    cfg.update(overrides)
    return cfg


class TestValidateFromDictBasics(unittest.TestCase):
    def setUp(self):
        self.v = ConfigValidator()

    def test_valid_minimal_config_passes(self):
        result = self.v.validate_from_dict(_minimal_valid_config())
        self.assertTrue(result["valid"], result["errors"])

    def test_missing_required_field_produces_error(self):
        cfg = _minimal_valid_config()
        del cfg["app_name"]
        result = self.v.validate_from_dict(cfg)
        self.assertFalse(result["valid"])
        self.assertTrue(any("app_name" in e for e in result["errors"]))

    def test_wrong_type_string_field_produces_error(self):
        cfg = _minimal_valid_config(app_name=123)
        result = self.v.validate_from_dict(cfg)
        self.assertFalse(result["valid"])

    def test_wrong_type_boolean_field_produces_error(self):
        cfg = _minimal_valid_config(debug="yes")  # should be bool
        result = self.v.validate_from_dict(cfg)
        self.assertFalse(result["valid"])

    def test_disallowed_language_produces_error(self):
        cfg = _minimal_valid_config(language="fr")
        result = self.v.validate_from_dict(cfg)
        self.assertFalse(result["valid"])
        self.assertTrue(any("language" in e for e in result["errors"]))

    def test_valid_version_pattern(self):
        cfg = _minimal_valid_config(version="2.10.3")
        result = self.v.validate_from_dict(cfg)
        self.assertTrue(result["valid"], result["errors"])

    def test_invalid_version_pattern_produces_error(self):
        cfg = _minimal_valid_config(version="1.0")  # missing patch
        result = self.v.validate_from_dict(cfg)
        self.assertFalse(result["valid"])

    def test_valid_config_returns_config_dict(self):
        result = self.v.validate_from_dict(_minimal_valid_config())
        self.assertIsNotNone(result["config"])
        self.assertIsInstance(result["config"], dict)

    def test_invalid_config_returns_none_config(self):
        cfg = _minimal_valid_config(language="xx")
        result = self.v.validate_from_dict(cfg)
        self.assertIsNone(result["config"])

    def test_result_has_required_keys(self):
        result = self.v.validate_from_dict(_minimal_valid_config())
        for key in ("valid", "errors", "warnings", "config"):
            self.assertIn(key, result)


class TestBooleanIntegerTypeCheck(unittest.TestCase):
    """REQ-CV-02: bool must not pass integer type check."""

    def setUp(self):
        self.v = ConfigValidator()
        self.v.add_custom_rule("test_port", {
            "type": "integer",
            "required": False,
            "min": 1,
            "max": 65535,
        })

    def test_integer_value_passes(self):
        cfg = _minimal_valid_config(test_port=8080)
        result = self.v.validate_from_dict(cfg)
        self.assertTrue(result["valid"], result["errors"])

    def test_true_rejected_as_integer(self):
        cfg = _minimal_valid_config(test_port=True)
        result = self.v.validate_from_dict(cfg)
        self.assertFalse(result["valid"])
        self.assertTrue(any("test_port" in e for e in result["errors"]))

    def test_false_rejected_as_integer(self):
        cfg = _minimal_valid_config(test_port=False)
        result = self.v.validate_from_dict(cfg)
        self.assertFalse(result["valid"])

    def test_zero_integer_accepted(self):
        self.v.add_custom_rule("zero_field", {"type": "integer", "required": False})
        cfg = _minimal_valid_config(zero_field=0)
        result = self.v.validate_from_dict(cfg)
        self.assertTrue(result["valid"], result["errors"])


class TestRateLimitingCrossFieldValidation(unittest.TestCase):
    """REQ-CV-01: _validate_password_policy called so rate_limiting checks execute."""

    def setUp(self):
        self.v = ConfigValidator()

    def _config_with_rate_limit(self, per_minute, per_hour, per_day):
        return _minimal_valid_config(rate_limiting={
            "enabled": True,
            "requests_per_minute": per_minute,
            "requests_per_hour": per_hour,
            "requests_per_day": per_day,
        })

    def test_valid_rate_limits_pass(self):
        cfg = self._config_with_rate_limit(60, 3600, 86400)
        result = self.v.validate_from_dict(cfg)
        self.assertTrue(result["valid"], result["errors"])

    def test_minute_greater_than_hour_produces_error(self):
        cfg = self._config_with_rate_limit(1000, 100, 10000)
        result = self.v.validate_from_dict(cfg)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("requests_per_hour" in e and "requests_per_minute" in e for e in result["errors"]),
            result["errors"]
        )

    def test_hour_greater_than_day_produces_error(self):
        cfg = self._config_with_rate_limit(10, 100, 50)  # hour(100) > day(50)
        result = self.v.validate_from_dict(cfg)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("requests_per_day" in e and "requests_per_hour" in e for e in result["errors"]),
            result["errors"]
        )


class TestIPValidation(unittest.TestCase):
    def setUp(self):
        self.v = ConfigValidator()

    def _security_config(self, allowed_ips=None, blocked_ips=None):
        return {
            "password_min_length": 12,
            "password_require_special": True,
            "password_require_numbers": True,
            "password_require_lowercase": True,
            "password_require_uppercase": True,
            "max_login_attempts": 5,
            "lockout_duration_minutes": 15,
            "enable_2fa": True,
            "enable_audit_log": True,
            "allowed_ips": allowed_ips or [],
            "blocked_ips": blocked_ips or [],
        }

    def test_valid_ipv4_cidr_in_allowed_ips(self):
        cfg = _minimal_valid_config(security=self._security_config(["192.168.1.0/24"]))
        result = self.v.validate_from_dict(cfg)
        self.assertTrue(result["valid"], result["errors"])

    def test_overlapping_allowed_and_blocked_ips_produces_error(self):
        cfg = _minimal_valid_config(
            security=self._security_config(["10.0.0.1"], ["10.0.0.1"])
        )
        result = self.v.validate_from_dict(cfg)
        self.assertFalse(result["valid"])

    def test_invalid_ip_in_allowed_ips_produces_error(self):
        cfg = _minimal_valid_config(security=self._security_config(["999.999.999.999"]))
        result = self.v.validate_from_dict(cfg)
        self.assertFalse(result["valid"])


class TestCustomRules(unittest.TestCase):
    def setUp(self):
        self.v = ConfigValidator()

    def test_add_and_validate_custom_string_rule(self):
        self.v.add_custom_rule("my_field", {
            "type": "string",
            "required": True,
            "min_length": 3,
            "max_length": 10,
        })
        result = self.v.validate_from_dict(_minimal_valid_config(my_field="hello"))
        self.assertTrue(result["valid"], result["errors"])

    def test_custom_rule_min_length_enforced(self):
        self.v.add_custom_rule("my_field", {
            "type": "string",
            "required": False,
            "min_length": 5,
        })
        result = self.v.validate_from_dict(_minimal_valid_config(my_field="ab"))
        self.assertFalse(result["valid"])

    def test_remove_rule_returns_true(self):
        self.v.add_custom_rule("tmp", {"type": "string", "required": False})
        self.assertTrue(self.v.remove_rule("tmp"))

    def test_remove_nonexistent_rule_returns_false(self):
        self.assertFalse(self.v.remove_rule("nonexistent_field"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
