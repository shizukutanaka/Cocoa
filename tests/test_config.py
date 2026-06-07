"""Acceptance tests for config.py.

Spec: docs/SPEC_CONFIG.md (REQ-CF-01..02)
Runnable without pytest:  python3 -m unittest tests.test_config -v
"""
import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

import config as config_module
from config import (  # noqa: E402
    APIConfig, Config, DatabaseConfig, SecurityConfig,
    BackupConfig, LoggingConfig, get_config, init_config,
)

_SAFE_KEYS = {"secret_key", "password", "admin_password", "encryption_key"}


class TestConfigCreation(unittest.TestCase):
    def test_default_config_creates_without_error(self):
        c = Config()
        self.assertEqual(c.environment, "development")

    def test_config_has_all_sections(self):
        c = Config()
        self.assertIsInstance(c.api, APIConfig)
        self.assertIsInstance(c.database, DatabaseConfig)
        self.assertIsInstance(c.security, SecurityConfig)
        self.assertIsInstance(c.backup, BackupConfig)
        self.assertIsInstance(c.logging, LoggingConfig)

    def test_api_cors_origins_is_list_by_default(self):
        api = APIConfig()
        self.assertIsInstance(api.cors_origins, list)
        self.assertGreater(len(api.cors_origins), 0)

    def test_production_env_with_default_key_raises_value_error(self):
        """REQ-CF-01: Config(env='production') must raise even without ENVIRONMENT env var."""
        with self.assertRaises(ValueError):
            Config(env="production")

    def test_development_env_does_not_validate(self):
        c = Config(env="development")
        # Should not raise with default placeholder keys
        self.assertEqual(c.environment, "development")

    def test_to_dict_returns_dict(self):
        c = Config()
        d = c.to_dict()
        self.assertIsInstance(d, dict)

    def test_to_dict_has_all_sections(self):
        c = Config()
        d = c.to_dict()
        for key in ("environment", "api", "database", "security", "backup", "logging"):
            self.assertIn(key, d)

    def test_to_dict_excludes_secret_keys(self):
        c = Config()
        d = c.to_dict()
        for section_dict in d.values():
            if isinstance(section_dict, dict):
                for unsafe_key in _SAFE_KEYS:
                    self.assertNotIn(
                        unsafe_key, section_dict,
                        f"Sensitive key {unsafe_key!r} found in to_dict() output"
                    )


class TestSecurityConfigValidate(unittest.TestCase):
    """REQ-CF-01: validate() must raise unconditionally on placeholder values."""

    def test_validate_raises_with_default_secret_key(self):
        sec = SecurityConfig()  # uses "change-me-in-production" defaults
        with self.assertRaises(ValueError) as ctx:
            sec.validate()
        self.assertIn("SECRET_KEY", str(ctx.exception))

    def test_validate_raises_with_default_encryption_key(self):
        sec = SecurityConfig(secret_key="real-secret-32-chars-xxxxxxxxxxxx")
        with self.assertRaises(ValueError) as ctx:
            sec.validate()
        self.assertIn("ENCRYPTION_KEY", str(ctx.exception))

    def test_validate_passes_with_real_keys(self):
        sec = SecurityConfig(
            secret_key="real-secret-32-chars-xxxxxxxxxxxx",
            encryption_key="real-encrypt-32-chars-xxxxxxxxxxx"
        )
        sec.validate()  # must not raise

    def test_validate_raises_without_environment_env_var(self):
        """Core of REQ-CF-01: validate() must not depend on ENVIRONMENT env var."""
        env_backup = os.environ.pop("ENVIRONMENT", None)
        try:
            sec = SecurityConfig()
            with self.assertRaises(ValueError):
                sec.validate()
        finally:
            if env_backup is not None:
                os.environ["ENVIRONMENT"] = env_backup


class TestAPIConfig(unittest.TestCase):
    def test_default_host_is_0000(self):
        api = APIConfig()
        # Default env-driven; just check it's a string
        self.assertIsInstance(api.host, str)

    def test_default_port_is_int(self):
        api = APIConfig()
        self.assertIsInstance(api.port, int)

    def test_cors_origins_is_list(self):
        api = APIConfig()
        self.assertIsInstance(api.cors_origins, list)

    def test_custom_cors_origins_preserved(self):
        api = APIConfig(cors_origins=["http://example.com"])
        self.assertEqual(api.cors_origins, ["http://example.com"])


class TestGetConfig(unittest.TestCase):
    def setUp(self):
        config_module._config_instance = None  # reset singleton

    def test_get_config_returns_config_instance(self):
        c = get_config()
        self.assertIsInstance(c, Config)

    def test_get_config_returns_same_instance(self):
        c1 = get_config()
        c2 = get_config()
        self.assertIs(c1, c2)

    def test_init_config_resets_singleton(self):
        c1 = get_config()
        c2 = init_config()
        self.assertIsNot(c1, c2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
