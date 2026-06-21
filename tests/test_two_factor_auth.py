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

    def test_verify_token_rejects_prefix_match(self):
        """verify_token must use constant-time comparison so a correct prefix does
        not pass; a 6-digit token must not accept a truncated or padded variant."""
        gen = self._make()
        code = gen.generate_token()
        # The exact match passes
        self.assertTrue(gen.verify_token(code))
        # A code that shares a prefix but differs later must not pass
        tweaked = code[:-1] + ("0" if code[-1] != "0" else "1")
        self.assertFalse(gen.verify_token(tweaked))


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


class TestDisable2FA(unittest.TestCase):
    """disable_2fa must never accept a hardcoded backdoor password."""

    def _mgr(self, db=None):
        from two_factor_auth import TwoFactorAuthManager
        return TwoFactorAuthManager(secret_key="k", db_manager=db)

    def test_no_verifier_fails_closed(self):
        """Without a verify_password callable, disable must fail — not accept any
        password (including the former hardcoded 'admin_password' backdoor)."""
        mgr = self._mgr()
        self.assertFalse(mgr.disable_2fa(1, "admin_password")["success"])
        self.assertFalse(mgr.disable_2fa(1, "any_password")["success"])

    def test_hardcoded_backdoor_no_longer_accepted(self):
        """'admin_password' was the old hardcoded universal backdoor; it must be
        rejected even when a db_manager is present but has no verify_password."""
        class DbWithoutVerifier:
            pass
        mgr = self._mgr(db=DbWithoutVerifier())
        self.assertFalse(mgr.disable_2fa(1, "admin_password")["success"])

    def test_correct_password_via_verifier_succeeds(self):
        """When verify_password returns True, disable must succeed."""
        class _DB:
            def verify_password(self, user_id, password):
                return password == "correct"
        mgr = self._mgr(db=_DB())
        self.assertTrue(mgr.disable_2fa(1, "correct")["success"])

    def test_wrong_password_via_verifier_fails(self):
        class _DB:
            def verify_password(self, user_id, password):
                return False
        mgr = self._mgr(db=_DB())
        self.assertFalse(mgr.disable_2fa(1, "wrong")["success"])


class TestTOTPReplayProtection(unittest.TestCase):
    """verify_2fa_token() must reject a TOTP code that was already used in the same window.

    Bug: the code called totp.verify_token() without tracking which codes had
    already been accepted, allowing an attacker to reuse a captured code multiple
    times within the same 30-second window.
    Fix: TwoFactorAuthManager._used_totp_tokens tracks (time_step, code) pairs
    per user; duplicate submissions within the valid window are rejected.
    """

    def _make_mgr(self):
        from two_factor_auth import TwoFactorAuthManager
        return TwoFactorAuthManager(secret_key="replay_test_key_abc123")

    def _mgr_with_user_secret(self):
        """Return a manager whose _get_user_secret() returns a fixed test secret."""
        from unittest.mock import patch
        from two_factor_auth import TwoFactorAuthManager, TOTPGenerator
        mgr = TwoFactorAuthManager(secret_key="replay_test_key_abc123")
        secret = mgr._generate_secret()
        # Inject the secret so _get_user_secret returns it
        with patch.object(mgr, '_get_user_secret', return_value=secret):
            totp = TOTPGenerator(secret)
            valid_token = totp.generate_token()
            # First call must succeed
            result1 = mgr.verify_2fa_token.__func__(mgr, 99, valid_token)
        # We need the patch active for both calls — re-do with longer context
        mgr2 = TwoFactorAuthManager(secret_key="replay_test_key_abc123")
        return mgr2, secret

    def test_same_token_rejected_on_second_use(self):
        from unittest.mock import patch
        from two_factor_auth import TwoFactorAuthManager, TOTPGenerator
        mgr = TwoFactorAuthManager(secret_key="replay_test_key_abc123")
        secret = mgr._generate_secret()

        with patch.object(mgr, '_get_user_secret', return_value=secret):
            totp = TOTPGenerator(secret)
            valid_token = totp.generate_token()

            result1 = mgr.verify_2fa_token(99, valid_token)
            result2 = mgr.verify_2fa_token(99, valid_token)

        self.assertTrue(result1['valid'], "First use of a valid token must succeed")
        self.assertFalse(result2['valid'], "Second use of same token in same window must fail")

    def test_different_users_same_token_independent(self):
        """Two different users' token tracking must not interfere."""
        from unittest.mock import patch
        from two_factor_auth import TwoFactorAuthManager, TOTPGenerator
        mgr = TwoFactorAuthManager(secret_key="replay_test_key_abc123")
        secret1 = mgr._generate_secret()
        secret2 = mgr._generate_secret()

        with patch.object(mgr, '_get_user_secret', side_effect=lambda uid: secret1 if uid == 1 else secret2):
            totp1 = TOTPGenerator(secret1)
            totp2 = TOTPGenerator(secret2)
            token1 = totp1.generate_token()
            token2 = totp2.generate_token()

            r1a = mgr.verify_2fa_token(1, token1)
            r2a = mgr.verify_2fa_token(2, token2)
            r1b = mgr.verify_2fa_token(1, token1)  # replay for user 1

        self.assertTrue(r1a['valid'])
        self.assertTrue(r2a['valid'])
        self.assertFalse(r1b['valid'], "Replay for user 1 must be rejected")


class TestTwoFactorAuthServiceFailsClosed(unittest.TestCase):
    """TwoFactorAuthService must refuse to start without COCOA_2FA_SECRET.

    A hardcoded fallback like `cocoa_2fa_secret_key_2025` would mean every
    deployment that forgot to set the env var shares the same key — anyone
    with read access to the source could decrypt all stored TOTP seeds.

    Fix: raise RuntimeError when the env var is missing or empty.
    """

    def test_raises_without_env_var(self):
        from two_factor_auth import TwoFactorAuthService
        saved = os.environ.pop("COCOA_2FA_SECRET", None)
        try:
            with self.assertRaises(RuntimeError) as ctx:
                TwoFactorAuthService()
            self.assertIn("COCOA_2FA_SECRET", str(ctx.exception))
        finally:
            if saved is not None:
                os.environ["COCOA_2FA_SECRET"] = saved

    def test_raises_with_empty_env_var(self):
        from two_factor_auth import TwoFactorAuthService
        saved = os.environ.get("COCOA_2FA_SECRET")
        os.environ["COCOA_2FA_SECRET"] = ""
        try:
            with self.assertRaises(RuntimeError):
                TwoFactorAuthService()
        finally:
            if saved is None:
                os.environ.pop("COCOA_2FA_SECRET", None)
            else:
                os.environ["COCOA_2FA_SECRET"] = saved

    def test_succeeds_with_env_var(self):
        from two_factor_auth import TwoFactorAuthService
        saved = os.environ.get("COCOA_2FA_SECRET")
        os.environ["COCOA_2FA_SECRET"] = "test-only-secret-not-for-production"
        try:
            svc = TwoFactorAuthService()
            self.assertEqual(svc.secret_key, "test-only-secret-not-for-production")
        finally:
            if saved is None:
                os.environ.pop("COCOA_2FA_SECRET", None)
            else:
                os.environ["COCOA_2FA_SECRET"] = saved

    def test_no_hardcoded_default_in_source(self):
        """Source must not contain the legacy hardcoded fallback."""
        import pathlib
        src = pathlib.Path("main/two_factor_auth.py").read_text()
        self.assertNotIn(
            "cocoa_2fa_secret_key_2025",
            src,
            "Legacy hardcoded 2FA secret default must be removed",
        )


if __name__ == '__main__':
    unittest.main()
