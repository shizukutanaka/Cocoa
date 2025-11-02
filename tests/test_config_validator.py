import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "main"))

from config_validator import ConfigValidator  # noqa: E402


class TestConfigValidator(unittest.TestCase):
    """`main/config_validator.py` の拡張検証ロジックを確認"""

    def setUp(self) -> None:
        self.validator = ConfigValidator()

    def _base_config(self) -> dict:
        return {
            "app_name": "Test Cocoa",
            "version": "1.2.3",
            "language": "ja",
            "debug": False,
            "log_level": "INFO",
        }

    def _security_block(self, overrides: dict | None = None) -> dict:
        block = {
            "password_min_length": 12,
            "password_require_special": True,
            "password_require_numbers": True,
            "password_require_uppercase": True,
            "max_login_attempts": 5,
            "lockout_duration_minutes": 15,
            "enable_2fa": True,
            "enable_audit_log": True,
            "allowed_ips": [],
            "blocked_ips": [],
        }
        if overrides:
            block.update(overrides)
        return block

    def _notification_block(self, overrides: dict | None = None) -> dict:
        block = {
            "enabled": False,
            "email": {
                "smtp_server": None,
                "smtp_port": 587,
                "from_address": None,
                "to_addresses": [],
            },
            "webhook": {
                "url": None,
                "method": "POST",
            },
        }
        if overrides:
            block.update(overrides)
        return block

    def _rate_limit_block(self, overrides: dict | None = None) -> dict:
        block = {
            "enabled": True,
            "requests_per_minute": 60,
            "requests_per_hour": 3600,
            "requests_per_day": 86400,
        }
        if overrides:
            block.update(overrides)
        return block

    def _billing_block(self, overrides: dict | None = None) -> dict:
        block = {
            "enabled": True,
            "mode": "subscription",
            "currency": "jpy",
            "default_price_tier": "standard",
            "tiers": {
                "standard": {
                    "price_id": "price_12345",
                    "description": "Standard plan",
                }
            },
            "checkout": {
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
            "webhook": {
                "enabled": True,
                "endpoint_secret_env": "STRIPE_WEBHOOK_SECRET",
            },
        }
        if overrides:
            block.update(overrides)
        return block

    def test_security_ip_normalization_and_errors(self) -> None:
        config = self._base_config()
        config["security"] = self._security_block(
            {
                "allowed_ips": ["192.168.0.1", "   ", "invalid"],
                "blocked_ips": ["10.0.0.0/24"],
            }
        )

        result = self.validator.validate_from_dict(config)

        self.assertFalse(result["valid"])
        self.assertTrue(
            any("security.allowed_ips[1]" in message for message in result["errors"]),
            msg="空文字列に対するエラーが検出されていません",
        )
        self.assertTrue(
            any("security.allowed_ips[2]" in message for message in result["errors"]),
            msg="無効なIP表現に対するエラーが検出されていません",
        )

    def test_security_ip_normalization_success(self) -> None:
        config = self._base_config()
        config["security"] = self._security_block(
            {
                "allowed_ips": ["192.168.0.1 ", "10.0.0.0/24"],
                "blocked_ips": ["172.16.0.0/16"],
            }
        )

        result = self.validator.validate_from_dict(config)

        self.assertTrue(result["valid"])
        normalized_allowed = result["config"]["security"]["allowed_ips"]
        self.assertEqual(normalized_allowed, ["192.168.0.1", "10.0.0.0/24"])

    def test_notification_requires_destination(self) -> None:
        config = self._base_config()
        config["security"] = self._security_block()
        config["notification"] = self._notification_block(
            {
                "enabled": True,
                "email": {
                    "smtp_server": "smtp.localhost",
                    "smtp_port": 587,
                    "from_address": None,
                    "to_addresses": [],
                },
                "webhook": {
                    "url": None,
                    "method": "POST",
                },
            }
        )

        result = self.validator.validate_from_dict(config)

        self.assertFalse(result["valid"])
        self.assertTrue(
            any("notification.email.from_address" in message for message in result["errors"]),
            msg="送信元アドレス欠如に対するエラーが検出されていません",
        )
        self.assertTrue(
            any("notification.email.to_addresses" in message for message in result["errors"]),
            msg="宛先欠如に対するエラーが検出されていません",
        )

    def test_notification_email_and_webhook_validation(self) -> None:
        config = self._base_config()
        config["security"] = self._security_block()
        config["notification"] = self._notification_block(
            {
                "enabled": True,
                "email": {
                    "smtp_server": "smtp.localhost",
                    "smtp_port": 2525,
                    "from_address": " admin@demo.local ",
                    "to_addresses": ["user1@demo.local ", "user2@demo.local"],
                },
                "webhook": {
                    "url": "https://localhost/hooks/cocoa",
                    "method": "POST",
                },
            }
        )

        result = self.validator.validate_from_dict(config)

        self.assertTrue(result["valid"])
        validated_email = result["config"]["notification"]["email"]
        self.assertEqual(validated_email["from_address"], "admin@demo.local")
        self.assertEqual(
            validated_email["to_addresses"], ["user1@demo.local", "user2@demo.local"]
        )

    def test_rate_limit_cross_threshold_warnings(self) -> None:
        config = self._base_config()
        config["security"] = self._security_block()
        config["notification"] = self._notification_block()
        config["rate_limiting"] = self._rate_limit_block(
            {
                "requests_per_minute": 10,
                "requests_per_hour": 500,
                "requests_per_day": 10000,
            }
        )

        result = self.validator.validate_from_dict(config)

        self.assertTrue(result["valid"])
        self.assertTrue(
            any("requests_per_minute * 60" in warning for warning in result["warnings"]),
            msg="時間当たりリクエストに関する警告が生成されていません",
        )
        self.assertTrue(
            any("requests_per_hour * 24" in warning for warning in result["warnings"]),
            msg="日単位リクエストに関する警告が生成されていません",
        )

    def test_billing_requires_price_ids_and_urls(self) -> None:
        config = self._base_config()
        config["security"] = self._security_block()
        config["billing"] = self._billing_block(
            {
                "tiers": {
                    "standard": {
                        "price_id": "invalid",
                    }
                },
                "checkout": {
                    "success_url": "ftp://example.com",
                    "cancel_url": "https://",
                },
            }
        )

        result = self.validator.validate_from_dict(config)

        self.assertFalse(result["valid"])
        self.assertTrue(
            any("billing.tiers.standard.price_id" in message for message in result["errors"]),
            msg="price_id が不正な場合のエラーを検知できていません",
        )
        self.assertTrue(
            any("billing.checkout.success_url" in message for message in result["errors"]),
            msg="success_url が不正な場合のエラーを検知できていません",
        )
        self.assertTrue(
            any("billing.checkout.cancel_url" in message for message in result["errors"]),
            msg="cancel_url が不正な場合のエラーを検知できていません",
        )

    def test_billing_valid_configuration_passes(self) -> None:
        config = self._base_config()
        config["security"] = self._security_block()
        config["billing"] = self._billing_block()

        result = self.validator.validate_from_dict(config)

        self.assertTrue(result["valid"])
        self.assertEqual(result["config"]["billing"]["mode"], "subscription")


if __name__ == "__main__":
    unittest.main()
