"""Tests for main/auth_manager.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "main")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auth_manager import (
    AuthError,
    AuthManager,
    UserStore,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing(unittest.TestCase):
    def test_hash_and_verify(self):
        h = hash_password("MyPass1")
        self.assertTrue(verify_password("MyPass1", h))

    def test_wrong_password_fails(self):
        h = hash_password("Correct1")
        self.assertFalse(verify_password("Wrong1", h))

    def test_hashes_are_unique(self):
        self.assertNotEqual(hash_password("Same1"), hash_password("Same1"))


class TestTokens(unittest.TestCase):
    def test_access_token_roundtrip(self):
        tok = create_access_token("uid1", "alice", "user")
        payload = decode_access_token(tok)
        self.assertEqual(payload["sub"], "uid1")
        self.assertEqual(payload["username"], "alice")
        self.assertEqual(payload["role"], "user")

    def test_refresh_token_roundtrip(self):
        tok = create_refresh_token("uid2")
        payload = decode_refresh_token(tok)
        self.assertEqual(payload["sub"], "uid2")

    def test_wrong_type_rejected(self):
        access = create_access_token("u", "alice", "user")
        with self.assertRaises((ValueError, Exception)):
            decode_refresh_token(access)

    def test_tampered_token_rejected(self):
        tok = create_access_token("u", "alice", "user")
        tampered = tok[:-4] + "XXXX"
        with self.assertRaises((ValueError, Exception)):
            decode_access_token(tampered)


class TestUserStore(unittest.TestCase):
    def setUp(self):
        self.store = UserStore()
        self.store.create_user("bob", "bob@x.com", hash_password("Bob1234!"), "user")

    def test_get_by_username(self):
        u = self.store.get_by_username("bob")
        self.assertIsNotNone(u)
        self.assertEqual(u.email, "bob@x.com")

    def test_get_by_email(self):
        u = self.store.get_by_email("bob@x.com")
        self.assertIsNotNone(u)
        self.assertEqual(u.username, "bob")

    def test_get_by_id(self):
        u = self.store.get_by_username("bob")
        u2 = self.store.get_by_id(u.user_id)
        self.assertEqual(u.user_id, u2.user_id)

    def test_duplicate_username_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_user("bob", "bob2@x.com", "h", "user")

    def test_duplicate_email_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_user("bob2", "bob@x.com", "h", "user")

    def test_delete_user(self):
        u = self.store.get_by_username("bob")
        ok = self.store.delete_user(u.user_id)
        self.assertTrue(ok)
        self.assertIsNone(self.store.get_by_username("bob"))

    def test_delete_nonexistent(self):
        self.assertFalse(self.store.delete_user("not-real"))

    def test_jti_revocation(self):
        self.store.revoke_jti("jti-abc")
        self.assertTrue(self.store.is_revoked("jti-abc"))
        self.assertFalse(self.store.is_revoked("jti-xyz"))

    def test_reset_token_lifecycle(self):
        u = self.store.get_by_username("bob")
        token = self.store.create_reset_token(u.user_id)
        uid = self.store.consume_reset_token(token)
        self.assertEqual(uid, u.user_id)
        # Can't reuse
        self.assertIsNone(self.store.consume_reset_token(token))

    def test_list_users(self):
        users = self.store.list_users()
        self.assertEqual(len(users), 1)


class TestAuthManager(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager()
        self.auth.register("alice", "alice@x.com", "Alice123!", "user")

    def test_register_and_login(self):
        tokens = self.auth.login("alice", "Alice123!")
        self.assertIsNotNone(tokens.access_token)
        self.assertIsNotNone(tokens.refresh_token)

    def test_verify_access_token(self):
        tokens = self.auth.login("alice", "Alice123!")
        payload = self.auth.verify_access_token(tokens.access_token)
        self.assertEqual(payload["username"], "alice")
        self.assertEqual(payload["role"], "user")

    def test_wrong_password_raises(self):
        with self.assertRaises(AuthError) as ctx:
            self.auth.login("alice", "wrong")
        self.assertEqual(ctx.exception.code, "invalid_credentials")

    def test_unknown_user_raises(self):
        with self.assertRaises(AuthError) as ctx:
            self.auth.login("nobody", "pass")
        self.assertEqual(ctx.exception.code, "invalid_credentials")

    def test_logout_revokes_token(self):
        tokens = self.auth.login("alice", "Alice123!")
        self.auth.logout(tokens.access_token, tokens.refresh_token)
        with self.assertRaises(AuthError) as ctx:
            self.auth.verify_access_token(tokens.access_token)
        self.assertEqual(ctx.exception.code, "token_revoked")

    def test_refresh_rotates_tokens(self):
        tokens = self.auth.login("alice", "Alice123!")
        new_tokens = self.auth.refresh(tokens.refresh_token)
        self.assertNotEqual(new_tokens.access_token, tokens.access_token)
        # Old refresh token is revoked
        with self.assertRaises(AuthError) as ctx:
            self.auth.refresh(tokens.refresh_token)
        self.assertEqual(ctx.exception.code, "token_revoked")

    def test_duplicate_registration_raises(self):
        with self.assertRaises(ValueError):
            self.auth.register("alice", "alice2@x.com", "Alice123!")

    def test_weak_password_rejected(self):
        with self.assertRaises(ValueError):
            self.auth.register("bob", "bob@x.com", "short")

    def test_password_no_digit_rejected(self):
        with self.assertRaises(ValueError):
            self.auth.register("carol", "carol@x.com", "NoDigitsHere")

    def test_account_lockout(self):
        import contextlib
        auth2 = AuthManager(max_failed_attempts=3)
        auth2.register("locked", "lock@x.com", "Lock1234!")
        for _ in range(3):
            with contextlib.suppress(AuthError):
                auth2.login("locked", "wrong")
        with self.assertRaises(AuthError) as ctx:
            auth2.login("locked", "Lock1234!")
        self.assertEqual(ctx.exception.code, "account_locked")

    def test_password_reset_flow(self):
        token = self.auth.request_password_reset("alice@x.com")
        self.assertIsNotNone(token)
        ok = self.auth.reset_password(token, "NewPass456!")
        self.assertTrue(ok)
        # Old password no longer works
        with self.assertRaises(AuthError):
            self.auth.login("alice", "Alice123!")
        # New password works
        tokens = self.auth.login("alice", "NewPass456!")
        self.assertIsNotNone(tokens.access_token)

    def test_password_reset_unknown_email(self):
        result = self.auth.request_password_reset("nobody@x.com")
        self.assertIsNone(result)

    def test_invalid_reset_token(self):
        ok = self.auth.reset_password("invalid-token", "NewPass456!")
        self.assertFalse(ok)

    def test_require_role_passes(self):
        tokens = self.auth.login("alice", "Alice123!")
        payload = self.auth.verify_access_token(tokens.access_token)
        self.auth.require_role(payload, "user", "admin")  # should not raise

    def test_require_role_fails(self):
        tokens = self.auth.login("alice", "Alice123!")
        payload = self.auth.verify_access_token(tokens.access_token)
        with self.assertRaises(AuthError) as ctx:
            self.auth.require_role(payload, "admin")
        self.assertEqual(ctx.exception.code, "forbidden")

    def test_change_role(self):
        self.auth.register("admin_user", "adm@x.com", "Admin123!", "admin")
        admin_tokens = self.auth.login("admin_user", "Admin123!")
        admin_payload = self.auth.verify_access_token(admin_tokens.access_token)
        user = self.auth.store.get_by_username("alice")
        self.auth.change_role(admin_payload, user.user_id, "moderator")
        updated = self.auth.store.get_by_id(user.user_id)
        self.assertEqual(updated.role, "moderator")


if __name__ == "__main__":
    unittest.main(verbosity=2)
