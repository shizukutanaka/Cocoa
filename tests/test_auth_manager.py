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


class TestChangePassword(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager()
        self.auth.register("cpuser", "cp@x.com", "OldPass1!")
        self.user_id = self.auth.store.get_by_username("cpuser").user_id

    def test_change_password_success(self):
        self.auth.change_password(self.user_id, "OldPass1!", "NewPass2@")
        tokens = self.auth.login("cpuser", "NewPass2@")
        self.assertIsNotNone(tokens.access_token)

    def test_wrong_current_password_raises(self):
        with self.assertRaises(AuthError) as ctx:
            self.auth.change_password(self.user_id, "WrongPass!", "NewPass2@")
        self.assertEqual(ctx.exception.code, "invalid_credentials")

    def test_weak_new_password_rejected(self):
        with self.assertRaises(ValueError):
            self.auth.change_password(self.user_id, "OldPass1!", "weak")

    def test_old_password_invalid_after_change(self):
        self.auth.change_password(self.user_id, "OldPass1!", "NewPass2@")
        with self.assertRaises(AuthError):
            self.auth.login("cpuser", "OldPass1!")

    def test_nonexistent_user_raises(self):
        with self.assertRaises(AuthError) as ctx:
            self.auth.change_password("no-such-id", "pass", "newpass")
        self.assertEqual(ctx.exception.code, "not_found")


class TestUserProfile(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager()
        self.auth.register("profileuser", "pu@x.com", "Profile1!")

    def _user_id(self):
        return self.auth.store.get_by_username("profileuser").user_id

    def test_update_display_name(self):
        user = self.auth.update_profile(self._user_id(), display_name="My Display Name")
        self.assertEqual(user.display_name, "My Display Name")

    def test_update_bio(self):
        user = self.auth.update_profile(self._user_id(), bio="Hello world")
        self.assertEqual(user.bio, "Hello world")

    def test_bio_truncated_at_500(self):
        user = self.auth.update_profile(self._user_id(), bio="x" * 600)
        self.assertLessEqual(len(user.bio), 500)

    def test_display_name_truncated_at_64(self):
        user = self.auth.update_profile(self._user_id(), display_name="x" * 100)
        self.assertLessEqual(len(user.display_name), 64)

    def test_public_profile_fields(self):
        user = self.auth.store.get_by_username("profileuser")
        profile = user.public_profile()
        for key in ("user_id", "username", "display_name", "bio", "avatar_url", "role", "created_at"):
            self.assertIn(key, profile)

    def test_public_profile_display_name_falls_back_to_username(self):
        user = self.auth.store.get_by_username("profileuser")
        profile = user.public_profile()
        self.assertEqual(profile["display_name"], "profileuser")

    def test_update_nonexistent_user_raises(self):
        with self.assertRaises(AuthError) as ctx:
            self.auth.update_profile("no-such-id", display_name="x")
        self.assertEqual(ctx.exception.code, "not_found")


class TestBookmarks(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager()
        self.auth.register("bkuser", "bk@x.com", "Bookm1234!")
        self.user_id = self.auth.store.get_by_username("bkuser").user_id

    def test_add_bookmark(self):
        bks = self.auth.add_bookmark(self.user_id, "listing-1")
        self.assertIn("listing-1", bks)

    def test_add_duplicate_is_idempotent(self):
        self.auth.add_bookmark(self.user_id, "listing-1")
        bks = self.auth.add_bookmark(self.user_id, "listing-1")
        self.assertEqual(bks.count("listing-1"), 1)

    def test_remove_bookmark(self):
        self.auth.add_bookmark(self.user_id, "listing-1")
        bks = self.auth.remove_bookmark(self.user_id, "listing-1")
        self.assertNotIn("listing-1", bks)

    def test_remove_nonexistent_bookmark_is_noop(self):
        bks = self.auth.remove_bookmark(self.user_id, "never-added")
        self.assertEqual(bks, [])

    def test_get_bookmarks_empty_on_new_user(self):
        bks = self.auth.get_bookmarks(self.user_id)
        self.assertEqual(bks, [])

    def test_bookmark_order_preserved(self):
        for i in range(5):
            self.auth.add_bookmark(self.user_id, f"item-{i}")
        bks = self.auth.get_bookmarks(self.user_id)
        self.assertEqual(bks, [f"item-{i}" for i in range(5)])

    def test_get_bookmarks_nonexistent_user_raises(self):
        with self.assertRaises(AuthError) as ctx:
            self.auth.get_bookmarks("no-such-id")
        self.assertEqual(ctx.exception.code, "not_found")


class TestFollowing(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager()
        self.auth.register("alice", "alice@x.com", "Alice1234!")
        self.auth.register("bob", "bob@x.com", "Bob12345!")
        self.alice = self.auth.store.get_by_username("alice").user_id
        self.bob = self.auth.store.get_by_username("bob").user_id

    def test_follow_creator(self):
        following = self.auth.follow(self.alice, self.bob)
        self.assertIn(self.bob, following)

    def test_follow_idempotent(self):
        self.auth.follow(self.alice, self.bob)
        following = self.auth.follow(self.alice, self.bob)
        self.assertEqual(following.count(self.bob), 1)

    def test_cannot_follow_self(self):
        with self.assertRaises(ValueError):
            self.auth.follow(self.alice, self.alice)

    def test_unfollow(self):
        self.auth.follow(self.alice, self.bob)
        following = self.auth.unfollow(self.alice, self.bob)
        self.assertNotIn(self.bob, following)

    def test_unfollow_not_following_is_noop(self):
        following = self.auth.unfollow(self.alice, self.bob)
        self.assertEqual(following, [])

    def test_get_following_returns_profiles(self):
        self.auth.follow(self.alice, self.bob)
        profiles = self.auth.get_following(self.alice)
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["username"], "bob")

    def test_get_following_empty(self):
        profiles = self.auth.get_following(self.alice)
        self.assertEqual(profiles, [])

    def test_followers_count(self):
        self.auth.follow(self.alice, self.bob)
        count = self.auth.get_followers_count(self.bob)
        self.assertEqual(count, 1)

    def test_follow_nonexistent_creator_raises(self):
        with self.assertRaises(AuthError) as ctx:
            self.auth.follow(self.alice, "no-such-id")
        self.assertEqual(ctx.exception.code, "not_found")


class TestEmailVerification(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager()
        self.user = self.auth.register("alice", "alice@example.com", "Passw0rd!")

    def test_new_user_not_verified(self):
        self.assertFalse(self.user.is_email_verified)

    def test_create_token_returns_string(self):
        token = self.auth.create_email_verification_token(self.user.user_id)
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 10)

    def test_verify_email_marks_verified(self):
        token = self.auth.create_email_verification_token(self.user.user_id)
        ok = self.auth.verify_email(token)
        self.assertTrue(ok)
        self.assertTrue(self.user.is_email_verified)

    def test_token_consumed_on_use(self):
        token = self.auth.create_email_verification_token(self.user.user_id)
        self.auth.verify_email(token)
        # Second use fails
        ok = self.auth.verify_email(token)
        self.assertFalse(ok)

    def test_invalid_token_returns_false(self):
        ok = self.auth.verify_email("invalid-token-xyz")
        self.assertFalse(ok)

    def test_public_profile_includes_verified_field(self):
        profile = self.user.public_profile()
        self.assertIn("is_email_verified", profile)
        self.assertFalse(profile["is_email_verified"])

    def test_public_profile_verified_after_confirm(self):
        token = self.auth.create_email_verification_token(self.user.user_id)
        self.auth.verify_email(token)
        profile = self.user.public_profile()
        self.assertTrue(profile["is_email_verified"])

    def test_multiple_tokens_can_be_created(self):
        t1 = self.auth.create_email_verification_token(self.user.user_id)
        t2 = self.auth.create_email_verification_token(self.user.user_id)
        self.assertNotEqual(t1, t2)
        # Either token should work
        ok = self.auth.verify_email(t2)
        self.assertTrue(ok)


class TestCreatorVerification(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager()
        self.admin_user = self.auth.register("admin", "admin@test.com", "Admin1234!", role="admin")
        self.admin_payload = {"sub": self.admin_user.user_id, "username": "admin", "role": "admin"}
        self.creator = self.auth.register("alice", "alice@test.com", "Passw0rd!")

    def test_new_user_not_verified(self):
        self.assertFalse(self.creator.is_creator_verified)

    def test_admin_can_verify_creator(self):
        user = self.auth.verify_creator(self.admin_payload, self.creator.user_id)
        self.assertTrue(user.is_creator_verified)

    def test_admin_can_revoke_verification(self):
        self.auth.verify_creator(self.admin_payload, self.creator.user_id)
        user = self.auth.revoke_creator_verification(self.admin_payload, self.creator.user_id)
        self.assertFalse(user.is_creator_verified)

    def test_non_admin_cannot_verify(self):
        non_admin = {"sub": self.creator.user_id, "username": "alice", "role": "user"}
        with self.assertRaises(AuthError):
            self.auth.verify_creator(non_admin, self.creator.user_id)

    def test_verify_nonexistent_user_raises(self):
        with self.assertRaises(AuthError) as ctx:
            self.auth.verify_creator(self.admin_payload, "no-such-id")
        self.assertEqual(ctx.exception.code, "not_found")

    def test_public_profile_includes_verified_flag(self):
        self.auth.verify_creator(self.admin_payload, self.creator.user_id)
        profile = self.creator.public_profile()
        self.assertIn("is_creator_verified", profile)
        self.assertTrue(profile["is_creator_verified"])


class TestUserSearch(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager()
        self.auth.register("alice", "alice@example.com", "Passw0rd!")
        self.auth.register("alicia", "alicia@example.com", "Passw0rd!")
        self.auth.register("bob", "bob@example.com", "Passw0rd!")

    def test_search_by_username(self):
        result = self.auth.search_users("alic")
        usernames = [u["username"] for u in result["items"]]
        self.assertIn("alice", usernames)
        self.assertIn("alicia", usernames)

    def test_search_excludes_non_matching(self):
        result = self.auth.search_users("alic")
        usernames = [u["username"] for u in result["items"]]
        self.assertNotIn("bob", usernames)

    def test_search_case_insensitive(self):
        result = self.auth.search_users("ALICE")
        self.assertGreater(result["total"], 0)

    def test_search_pagination_fields_present(self):
        result = self.auth.search_users("a", limit=1, offset=0)
        for key in ("total", "offset", "limit", "has_more", "next_offset", "items"):
            self.assertIn(key, result)

    def test_search_has_more_pagination(self):
        result = self.auth.search_users("a", limit=1, offset=0)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 1)

    def test_search_returns_public_profile_fields(self):
        result = self.auth.search_users("alice")
        for key in ("user_id", "username", "role"):
            self.assertIn(key, result["items"][0])

    def test_search_no_results(self):
        result = self.auth.search_users("zzz_no_match")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])


class TestApiKeyManagement(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager()
        self.user = self.auth.register("alice", "alice@example.com", "Passw0rd!")

    def test_create_api_key_returns_raw_key(self):
        result = self.auth.create_api_key(self.user.user_id, "My Key")
        self.assertIn("raw_key", result)
        self.assertTrue(result["raw_key"].startswith("cca_"))

    def test_create_api_key_returns_metadata(self):
        result = self.auth.create_api_key(self.user.user_id, "My Key")
        for f in ("key_id", "name", "key_prefix", "created_at", "last_used"):
            self.assertIn(f, result)
        self.assertNotIn("key_hash", result)

    def test_raw_key_not_stored(self):
        result = self.auth.create_api_key(self.user.user_id, "My Key")
        listed = self.auth.list_api_keys(self.user.user_id)
        entry = next(e for e in listed if e["key_id"] == result["key_id"])
        self.assertNotIn("raw_key", entry)
        self.assertNotIn("key_hash", entry)

    def test_verify_api_key_valid(self):
        result = self.auth.create_api_key(self.user.user_id, "My Key")
        payload = self.auth.verify_api_key(result["raw_key"])
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], self.user.user_id)
        self.assertEqual(payload["type"], "api_key")

    def test_verify_api_key_invalid(self):
        self.assertIsNone(self.auth.verify_api_key("cca_invalidkey"))

    def test_list_api_keys_scoped_to_user(self):
        user2 = self.auth.register("bob", "bob@example.com", "Passw0rd!")
        self.auth.create_api_key(self.user.user_id, "Alice Key")
        self.auth.create_api_key(user2.user_id, "Bob Key")
        alice_keys = self.auth.list_api_keys(self.user.user_id)
        self.assertEqual(len(alice_keys), 1)
        self.assertEqual(alice_keys[0]["name"], "Alice Key")

    def test_revoke_api_key_removes_it(self):
        result = self.auth.create_api_key(self.user.user_id, "Temp Key")
        ok = self.auth.revoke_api_key(self.user.user_id, result["key_id"])
        self.assertTrue(ok)
        self.assertEqual(self.auth.list_api_keys(self.user.user_id), [])

    def test_revoke_invalid_key_returns_false(self):
        self.assertFalse(self.auth.revoke_api_key(self.user.user_id, "no-such-key"))

    def test_revoke_another_users_key_fails(self):
        user2 = self.auth.register("bob", "bob@example.com", "Passw0rd!")
        result = self.auth.create_api_key(user2.user_id, "Bob Key")
        self.assertFalse(self.auth.revoke_api_key(self.user.user_id, result["key_id"]))

    def test_multiple_keys_per_user(self):
        self.auth.create_api_key(self.user.user_id, "Key A")
        self.auth.create_api_key(self.user.user_id, "Key B")
        self.assertEqual(len(self.auth.list_api_keys(self.user.user_id)), 2)

    def test_verify_updates_last_used(self):
        result = self.auth.create_api_key(self.user.user_id, "Track Key")
        self.auth.verify_api_key(result["raw_key"])
        keys = self.auth.list_api_keys(self.user.user_id)
        entry = next(e for e in keys if e["key_id"] == result["key_id"])
        self.assertIsNotNone(entry["last_used"])

    def test_create_api_key_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self.auth.create_api_key(self.user.user_id, "  ")

    def test_create_api_key_unknown_user_raises(self):
        with self.assertRaises(AuthError):
            self.auth.create_api_key("no-such-user", "Key")


if __name__ == "__main__":
    unittest.main(verbosity=2)
