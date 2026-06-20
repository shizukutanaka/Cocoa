"""Tests for two_factor_auth module."""
import base64
import os
import secrets
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


class TestTOTPGenerator(unittest.TestCase):
    def _make(self, secret=None):
        from two_factor_auth import TOTPGenerator
        if secret is None:
            secret = base64.b32encode(secrets.token_bytes(20)).decode()
        return TOTPGenerator(secret)

    def test_generate_returns_digits(self):
        gen = self._make()
        code = gen.generate_token()
        self.assertIsInstance(code, str)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_verify_current_code(self):
        gen = self._make()
        code = gen.generate_token()
        self.assertTrue(gen.verify_token(code))

    def test_verify_wrong_code(self):
        gen = self._make()
        self.assertFalse(gen.verify_token("000000"))

    def test_custom_digits(self):
        from two_factor_auth import TOTPGenerator
        secret = base64.b32encode(secrets.token_bytes(20)).decode()
        gen = TOTPGenerator(secret, digits=8)
        code = gen.generate_token()
        self.assertEqual(len(code), 8)

    def test_generate_is_deterministic_same_interval(self):
        secret = base64.b32encode(secrets.token_bytes(20)).decode()
        from two_factor_auth import TOTPGenerator
        gen = TOTPGenerator(secret, interval=30)
        # Within same interval, two calls should return same code
        c1 = gen.generate_token()
        c2 = gen.generate_token()
        self.assertEqual(c1, c2)


class TestTwoFactorAuthManager(unittest.TestCase):
    def _make(self, secret_key="test_secret_key_12345"):
        from two_factor_auth import TwoFactorAuthManager
        return TwoFactorAuthManager(secret_key=secret_key)

    def test_init(self):
        mgr = self._make()
        self.assertIsNotNone(mgr)

    def test_generate_secret(self):
        mgr = self._make()
        secret = mgr._generate_secret()
        self.assertIsInstance(secret, str)
        self.assertGreater(len(secret), 0)

    def test_generate_secrets_unique(self):
        mgr = self._make()
        s1 = mgr._generate_secret()
        s2 = mgr._generate_secret()
        self.assertNotEqual(s1, s2)

    def test_generate_qr_uri(self):
        mgr = self._make()
        secret = mgr._generate_secret()
        uri = mgr.generate_qr_code_uri("testuser", secret)
        self.assertIn("otpauth://totp/", uri)
        self.assertIn(secret, uri)

    def test_backup_codes_count(self):
        mgr = self._make()
        codes = mgr._generate_backup_codes()
        self.assertIsInstance(codes, list)
        self.assertGreater(len(codes), 0)

    def test_backup_codes_unique(self):
        mgr = self._make()
        codes = mgr._generate_backup_codes()
        self.assertEqual(len(codes), len(set(codes)))

    def test_issuer_name_set(self):
        mgr = self._make()
        self.assertIsInstance(mgr.issuer_name, str)
        self.assertGreater(len(mgr.issuer_name), 0)

    def test_verify_fails_closed_without_db(self):
        # No persistence wired → no per-user secret → verification must DENY,
        # never accept a hardcoded global secret (closed backdoor).
        from two_factor_auth import TOTPGenerator
        mgr = self._make()
        # A token generated from the old hardcoded secret must NOT pass.
        backdoor = TOTPGenerator("JBSWY3DPEHPK3PXP").generate_token()
        self.assertFalse(mgr.verify_2fa_token(1, backdoor)["valid"])
        # Old hardcoded backup codes must NOT pass either.
        for code in ("12345678", "87654321", "11111111"):
            self.assertFalse(mgr.verify_backup_code(1, code)["valid"])
        self.assertFalse(mgr.enable_2fa(1, "alice", backdoor)["success"])

    def test_verify_uses_per_user_secret_when_available(self):
        # With a persistence layer exposing the user's real secret, a token from
        # THAT secret passes and a token from a different secret fails.
        from two_factor_auth import TOTPGenerator
        user_secret = "KVKFKRCPNZQUYMLXOVYDSQKJKZDTSRLD"

        class _DB:
            def get_two_factor_secret(self, user_id):
                return user_secret if user_id == 7 else None
            def get_two_factor_backup_codes(self, user_id):
                return ["AAAA1111"] if user_id == 7 else []

        from two_factor_auth import TwoFactorAuthManager
        mgr = TwoFactorAuthManager(secret_key="k", db_manager=_DB())
        good = TOTPGenerator(user_secret).generate_token()
        self.assertTrue(mgr.verify_2fa_token(7, good)["valid"])
        other = TOTPGenerator("JBSWY3DPEHPK3PXP").generate_token()
        self.assertFalse(mgr.verify_2fa_token(7, other)["valid"])
        # Unknown user (no secret) still fails closed.
        self.assertFalse(mgr.verify_2fa_token(99, good)["valid"])
        # Per-user backup code works; wrong one doesn't.
        self.assertTrue(mgr.verify_backup_code(7, "AAAA1111")["valid"])
        self.assertFalse(mgr.verify_backup_code(7, "12345678")["valid"])


if __name__ == '__main__':
    unittest.main()
