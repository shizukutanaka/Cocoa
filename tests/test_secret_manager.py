"""Acceptance tests for secret_manager.py (EnvironmentSecretManager).

Spec: docs/SPEC_SECRET_MANAGER.md (REQ-SM-01..02)
Runnable without pytest:  python3 -m unittest tests.test_secret_manager -v
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

from secret_manager import (  # noqa: E402
    EnvironmentSecretManager,
    SecretManagerFactory,
    SecretProvider,
    get_secret_manager,
)


class TestEnvironmentSecretManager(unittest.TestCase):
    def setUp(self):
        self.mgr = EnvironmentSecretManager()

    def test_set_and_get_roundtrip(self):
        self.mgr.set_secret("TEST_KEY", "secret_value")
        self.assertEqual(self.mgr.get_secret("TEST_KEY"), "secret_value")

    def test_get_missing_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.mgr.get_secret("DEFINITELY_NOT_SET_XYZ_99")

    def test_set_then_list_contains_key(self):
        self.mgr.set_secret("LISTED_KEY", "val")
        self.assertIn("LISTED_KEY", self.mgr.list_secrets())

    def test_list_secrets_without_cocoa_prefix(self):
        self.mgr.set_secret("NO_PREFIX_KEY", "value")
        self.assertIn("NO_PREFIX_KEY", self.mgr.list_secrets())

    def test_multiple_secrets_all_listed(self):
        self.mgr.set_secret("K1", "v1")
        self.mgr.set_secret("K2", "v2")
        secrets = self.mgr.list_secrets()
        self.assertIn("K1", secrets)
        self.assertIn("K2", secrets)

    def test_delete_removes_secret(self):
        self.mgr.set_secret("DEL_KEY", "gone")
        self.mgr.delete_secret("DEL_KEY")
        with self.assertRaises(KeyError):
            self.mgr.get_secret("DEL_KEY")

    def test_delete_removes_from_list(self):
        self.mgr.set_secret("DEL_LIST", "v")
        self.mgr.delete_secret("DEL_LIST")
        self.assertNotIn("DEL_LIST", self.mgr.list_secrets())

    def test_delete_nonexistent_returns_true(self):
        result = self.mgr.delete_secret("GHOST_KEY_XYZ")
        self.assertTrue(result)

    def test_rotate_updates_value(self):
        self.mgr.set_secret("ROT_KEY", "old_value")
        self.mgr.rotate_secret("ROT_KEY", "new_value")
        self.assertEqual(self.mgr.get_secret("ROT_KEY"), "new_value")

    def test_set_returns_true(self):
        result = self.mgr.set_secret("SET_TRUE", "v")
        self.assertTrue(result)

    def test_overwrite_existing_key(self):
        self.mgr.set_secret("OVR", "first")
        self.mgr.set_secret("OVR", "second")
        self.assertEqual(self.mgr.get_secret("OVR"), "second")

    def test_empty_string_value_stored_and_retrieved(self):
        self.mgr.set_secret("EMPTY_VAL", "")
        self.assertEqual(self.mgr.get_secret("EMPTY_VAL"), "")

    def test_list_secrets_returns_list(self):
        self.assertIsInstance(self.mgr.list_secrets(), list)


class TestGetSecretManager(unittest.TestCase):
    def test_env_provider_returns_environment_manager(self):
        mgr = get_secret_manager("env")
        self.assertIsInstance(mgr, EnvironmentSecretManager)

    def test_unknown_provider_raises_value_error(self):
        with self.assertRaises(ValueError):
            get_secret_manager("bogus_provider")

    def test_unknown_provider_error_message_includes_name(self):
        try:
            get_secret_manager("typo_name")
        except ValueError as e:
            self.assertIn("typo_name", str(e))
        else:
            self.fail("Expected ValueError")

    def test_uppercase_provider_accepted(self):
        mgr = get_secret_manager("ENV")
        self.assertIsInstance(mgr, EnvironmentSecretManager)


class TestSecretManagerFactory(unittest.TestCase):
    def test_factory_creates_environment_manager(self):
        mgr = SecretManagerFactory.create(SecretProvider.ENVIRONMENT)
        self.assertIsInstance(mgr, EnvironmentSecretManager)

    def test_factory_unsupported_provider_raises(self):
        with self.assertRaises(ValueError):
            SecretManagerFactory.create(SecretProvider.AZURE_KEY_VAULT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
