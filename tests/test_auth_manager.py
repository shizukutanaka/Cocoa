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

    def test_concurrent_create_reset_token_no_crash(self):
        # Many parallel reset requests for one user must not KeyError on the
        # purge of prior tokens, and must leave exactly one usable token.
        import threading
        u = self.store.get_by_username("bob")
        barrier = threading.Barrier(16)
        issued = []
        lock = threading.Lock()

        def make():
            barrier.wait()
            tok = self.store.create_reset_token(u.user_id)
            with lock:
                issued.append(tok)

        threads = [threading.Thread(target=make) for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(issued), 16)
        # Only the last-stored token survives the purge; exactly one consumes.
        valid = [t for t in issued if self.store.consume_reset_token(t) is not None]
        self.assertEqual(len(valid), 1)

    def test_verify_token_create_prunes_expired(self):
        # An expired verify token must be pruned when a new one is created so the
        # map doesn't grow without bound.
        import time as _time
        u = self.store.get_by_username("bob")
        stale = self.store.create_verify_token(u.user_id)
        # Force the stale token to be expired in the store.
        self.store._verify_tokens[stale] = (u.user_id, _time.time() - 1)
        self.store.create_verify_token(u.user_id)
        self.assertNotIn(stale, self.store._verify_tokens)

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

    def test_concurrent_refresh_mints_one_session(self):
        # A refresh token used by 16 threads at once must rotate exactly once:
        # only one caller gets a new pair, the rest are rejected as revoked.
        # (Closes the check-then-revoke replay race.)
        import threading
        tokens = self.auth.login("alice", "Alice123!")
        barrier = threading.Barrier(16)
        successes = []
        rejected = []
        lock = threading.Lock()

        def do_refresh():
            barrier.wait()
            try:
                pair = self.auth.refresh(tokens.refresh_token)
                with lock:
                    successes.append(pair)
            except AuthError as e:
                with lock:
                    rejected.append(e.code)

        threads = [threading.Thread(target=do_refresh) for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(successes), 1, "exactly one refresh may succeed")
        self.assertEqual(len(rejected), 15)
        self.assertTrue(all(code == "token_revoked" for code in rejected))

    def test_claim_jti_revocation_is_single_winner(self):
        # Direct store-level check of the atomic claim primitive.
        store = self.auth.store
        self.assertTrue(store.claim_jti_revocation("jti-x"))
        self.assertFalse(store.claim_jti_revocation("jti-x"))  # already claimed
        self.assertTrue(store.is_revoked("jti-x"))

    def test_duplicate_registration_raises(self):
        with self.assertRaises(ValueError):
            self.auth.register("alice", "alice2@x.com", "Alice123!")

    def test_username_uniqueness_is_case_insensitive(self):
        # "Alice" must collide with the existing "alice" (anti-impersonation).
        with self.assertRaises(ValueError):
            self.auth.register("Alice", "other@x.com", "Alice123!")

    def test_login_is_case_insensitive_on_username(self):
        tokens = self.auth.login("ALICE", "Alice123!")
        self.assertIsNotNone(tokens.access_token)

    def test_email_uniqueness_is_case_insensitive(self):
        # Same mailbox with different casing must not create a second account.
        with self.assertRaises(ValueError):
            self.auth.register("alice2", "Alice@X.com", "Alice123!")

    def test_email_normalized_to_lowercase(self):
        user = self.auth.register("mixedcase", "Mixed@CASE.Com", "Mixed123!")
        self.assertEqual(user.email, "mixed@case.com")
        # Reset-by-email must find it regardless of the casing supplied.
        self.assertIsNotNone(self.auth.request_password_reset("MIXED@case.com"))

    def test_username_whitespace_trimmed(self):
        user = self.auth.register("  spacey  ", "spacey@x.com", "Spacey12!")
        self.assertEqual(user.username, "spacey")
        self.assertIsNotNone(self.auth.login("spacey", "Spacey12!").access_token)

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

    def test_reset_token_invalidates_previous(self):
        # Second request_password_reset must cancel the first token so it can't
        # be used (prevents stale-token takeover after the user has re-requested).
        t1 = self.auth.request_password_reset("alice@x.com")
        t2 = self.auth.request_password_reset("alice@x.com")
        self.assertFalse(self.auth.reset_password(t1, "NewPass456!"))
        self.assertTrue(self.auth.reset_password(t2, "NewPass456!"))

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

    def test_concurrent_add_same_bookmark_no_duplicate(self):
        import threading
        barrier = threading.Barrier(20)

        def add():
            barrier.wait()
            self.auth.add_bookmark(self.user_id, "listing-1")

        threads = [threading.Thread(target=add) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        bks = self.auth.get_bookmarks(self.user_id)
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

    def test_bookmark_limit_enforced(self):
        import auth_manager as am
        orig = am._MAX_BOOKMARKS
        am._MAX_BOOKMARKS = 3
        try:
            for i in range(3):
                self.auth.add_bookmark(self.user_id, f"item-{i}")
            with self.assertRaises(ValueError):
                self.auth.add_bookmark(self.user_id, "item-overflow")
        finally:
            am._MAX_BOOKMARKS = orig


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

    def test_concurrent_follow_no_duplicate(self):
        # 20 threads all follow bob at once; the entry must appear exactly once
        # (the check-and-append is locked), so a single unfollow fully removes it.
        import threading
        barrier = threading.Barrier(20)

        def do_follow():
            barrier.wait()  # maximize contention on the check-and-append
            self.auth.follow(self.alice, self.bob)

        threads = [threading.Thread(target=do_follow) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        following = self.auth.get_following(self.alice)
        self.assertEqual(len(following), 1)
        # One unfollow must leave no residual duplicate.
        remaining = self.auth.unfollow(self.alice, self.bob)
        self.assertNotIn(self.bob, remaining)

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

    def test_follow_limit_enforced(self):
        import auth_manager as am
        orig = am._MAX_FOLLOWING
        am._MAX_FOLLOWING = 1
        try:
            self.auth.follow(self.alice, self.bob)
            # register a third user; alice is already at the limit
            self.auth.register("charlie", "charlie@x.com", "Charlie1!")
            charlie = self.auth.store.get_by_username("charlie").user_id
            with self.assertRaises(ValueError):
                self.auth.follow(self.alice, charlie)
        finally:
            am._MAX_FOLLOWING = orig


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

    def test_api_key_limit_enforced(self):
        orig = self.auth.store._MAX_API_KEYS_PER_USER
        self.auth.store._MAX_API_KEYS_PER_USER = 2
        try:
            self.auth.create_api_key(self.user.user_id, "Key 1")
            self.auth.create_api_key(self.user.user_id, "Key 2")
            with self.assertRaises(ValueError):
                self.auth.create_api_key(self.user.user_id, "Key 3")
        finally:
            self.auth.store._MAX_API_KEYS_PER_USER = orig

    def test_revoke_then_create_within_limit(self):
        orig = self.auth.store._MAX_API_KEYS_PER_USER
        self.auth.store._MAX_API_KEYS_PER_USER = 1
        try:
            k = self.auth.create_api_key(self.user.user_id, "Key 1")
            self.auth.revoke_api_key(self.user.user_id, k["key_id"])
            # after revoke, slot is free
            self.auth.create_api_key(self.user.user_id, "Key 2")
        finally:
            self.auth.store._MAX_API_KEYS_PER_USER = orig


class TestGetFollowers(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager()
        self.auth.register("alice", "alice@x.com", "Alice1234!")
        self.auth.register("bob", "bob@x.com", "Bob12345!")
        self.auth.register("carol", "carol@x.com", "Carol123!")
        self.alice = self.auth.store.get_by_username("alice").user_id
        self.bob = self.auth.store.get_by_username("bob").user_id
        self.carol = self.auth.store.get_by_username("carol").user_id

    def test_no_followers_initially(self):
        followers = self.auth.get_followers(self.alice)
        self.assertEqual(followers, [])

    def test_followers_after_follow(self):
        self.auth.follow(self.bob, self.alice)
        followers = self.auth.get_followers(self.alice)
        self.assertEqual(len(followers), 1)
        self.assertEqual(followers[0]["username"], "bob")

    def test_multiple_followers(self):
        self.auth.follow(self.bob, self.alice)
        self.auth.follow(self.carol, self.alice)
        followers = self.auth.get_followers(self.alice)
        self.assertEqual(len(followers), 2)

    def test_unfollow_removes_from_followers(self):
        self.auth.follow(self.bob, self.alice)
        self.auth.unfollow(self.bob, self.alice)
        followers = self.auth.get_followers(self.alice)
        self.assertEqual(followers, [])

    def test_followers_returns_public_profiles(self):
        self.auth.follow(self.bob, self.alice)
        followers = self.auth.get_followers(self.alice)
        for key in ("user_id", "username"):
            self.assertIn(key, followers[0])

    def test_get_followers_unknown_user_raises(self):
        with self.assertRaises(AuthError):
            self.auth.get_followers("no-such-id")

    def test_followers_independent_per_user(self):
        self.auth.follow(self.bob, self.alice)
        carol_followers = self.auth.get_followers(self.carol)
        self.assertEqual(carol_followers, [])


class TestGetUsersWhoBokmarked(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager()
        self.auth.register("alice", "alice@x.com", "Alice1234!")
        self.auth.register("bob", "bob@x.com", "Bob12345!")
        self.alice = self.auth.store.get_by_username("alice").user_id
        self.bob = self.auth.store.get_by_username("bob").user_id

    def test_no_bookmarks_initially(self):
        users = self.auth.get_users_who_bookmarked("item1")
        self.assertEqual(users, [])

    def test_finds_user_after_bookmark(self):
        self.auth.add_bookmark(self.alice, "item1")
        users = self.auth.get_users_who_bookmarked("item1")
        self.assertIn(self.alice, users)

    def test_multiple_users_with_same_bookmark(self):
        self.auth.add_bookmark(self.alice, "item1")
        self.auth.add_bookmark(self.bob, "item1")
        users = self.auth.get_users_who_bookmarked("item1")
        self.assertEqual(len(users), 2)

    def test_excludes_user_after_unbookmark(self):
        self.auth.add_bookmark(self.alice, "item1")
        self.auth.remove_bookmark(self.alice, "item1")
        users = self.auth.get_users_who_bookmarked("item1")
        self.assertNotIn(self.alice, users)

    def test_different_items_independent(self):
        self.auth.add_bookmark(self.alice, "item1")
        users = self.auth.get_users_who_bookmarked("item2")
        self.assertNotIn(self.alice, users)


class TestSocialLinks(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager()
        self.user = self.auth.register("alice", "alice@x.com", "Alice1234!")
        self.uid = self.user.user_id

    def test_website_url_saved(self):
        user = self.auth.update_profile(self.uid, website_url="https://example.com")
        self.assertEqual(user.website_url, "https://example.com")

    def test_social_links_saved(self):
        user = self.auth.update_profile(self.uid, social_links={"twitter": "@alice"})
        self.assertEqual(user.social_links["twitter"], "@alice")

    def test_social_links_unknown_key_filtered(self):
        user = self.auth.update_profile(self.uid, social_links={"discord": "alice#1234"})
        self.assertNotIn("discord", user.social_links)

    def test_social_links_replaces_previous(self):
        self.auth.update_profile(self.uid, social_links={"twitter": "@alice"})
        user = self.auth.update_profile(self.uid, social_links={"github": "alice-gh"})
        self.assertNotIn("twitter", user.social_links)
        self.assertIn("github", user.social_links)

    def test_social_links_empty_clears(self):
        self.auth.update_profile(self.uid, social_links={"twitter": "@alice"})
        user = self.auth.update_profile(self.uid, social_links={})
        self.assertEqual(user.social_links, {})

    def test_social_links_in_public_profile(self):
        self.auth.update_profile(self.uid, social_links={"vrchat": "alice_vrc"})
        profile = self.user.public_profile()
        self.assertIn("social_links", profile)
        self.assertEqual(profile["social_links"]["vrchat"], "alice_vrc")

    def test_website_url_in_public_profile(self):
        self.auth.update_profile(self.uid, website_url="https://alice.dev")
        profile = self.user.public_profile()
        self.assertIn("website_url", profile)
        self.assertEqual(profile["website_url"], "https://alice.dev")

    def test_none_social_links_does_not_clear(self):
        self.auth.update_profile(self.uid, social_links={"twitter": "@alice"})
        user = self.auth.update_profile(self.uid, bio="Hello")  # social_links not passed
        self.assertIn("twitter", user.social_links)


class TestCreatorApplications(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager()
        self.auth.register("creator1", "c1@x.com", "Creator1!")
        self.auth.register("creator2", "c2@x.com", "Creator2!")
        self.uid1 = self.auth.store.get_by_username("creator1").user_id
        self.uid2 = self.auth.store.get_by_username("creator2").user_id
        self.auth.register("admin_u", "admin@x.com", "Admin123!")
        admin_user = self.auth.store.get_by_username("admin_u")
        admin_user.role = "admin"
        self.admin_id = admin_user.user_id
        self.admin_payload = {"sub": self.admin_id, "role": "admin"}

    def test_submit_application_succeeds(self):
        app = self.auth.submit_creator_application(self.uid1, "I make great avatars", "https://portfolio.example")
        self.assertEqual(app.user_id, self.uid1)
        self.assertEqual(app.status, "pending")
        self.assertIsNotNone(app.application_id)

    def test_submit_application_empty_reason_raises(self):
        with self.assertRaises(ValueError):
            self.auth.submit_creator_application(self.uid1, "   ")

    def test_submit_duplicate_pending_raises(self):
        self.auth.submit_creator_application(self.uid1, "First application")
        with self.assertRaises(ValueError):
            self.auth.submit_creator_application(self.uid1, "Second application")

    def test_already_verified_raises(self):
        user = self.auth.store.get_by_id(self.uid1)
        user.is_creator_verified = True
        with self.assertRaises(ValueError):
            self.auth.submit_creator_application(self.uid1, "Already verified")

    def test_unknown_user_raises(self):
        with self.assertRaises(AuthError):
            self.auth.submit_creator_application("no-such-id", "reason")

    def test_approve_application(self):
        app = self.auth.submit_creator_application(self.uid1, "Great portfolio")
        result = self.auth.review_creator_application(self.admin_payload, app.application_id, "approved", "Looks good")
        self.assertEqual(result.status, "approved")
        user = self.auth.store.get_by_id(self.uid1)
        self.assertTrue(user.is_creator_verified)

    def test_reject_application(self):
        app = self.auth.submit_creator_application(self.uid1, "My work")
        result = self.auth.review_creator_application(self.admin_payload, app.application_id, "rejected", "Not enough")
        self.assertEqual(result.status, "rejected")
        user = self.auth.store.get_by_id(self.uid1)
        self.assertFalse(user.is_creator_verified)

    def test_invalid_decision_raises(self):
        app = self.auth.submit_creator_application(self.uid1, "reason")
        with self.assertRaises(ValueError):
            self.auth.review_creator_application(self.admin_payload, app.application_id, "maybe")

    def test_review_unknown_application_raises(self):
        with self.assertRaises(ValueError):
            self.auth.review_creator_application(self.admin_payload, "no-such-id", "approved")

    def test_review_already_decided_raises(self):
        app = self.auth.submit_creator_application(self.uid1, "reason")
        self.auth.review_creator_application(self.admin_payload, app.application_id, "approved")
        with self.assertRaises(ValueError):
            self.auth.review_creator_application(self.admin_payload, app.application_id, "rejected")

    def test_non_admin_review_raises(self):
        app = self.auth.submit_creator_application(self.uid1, "reason")
        user_payload = {"sub": self.uid2, "role": "user"}
        with self.assertRaises(AuthError):
            self.auth.review_creator_application(user_payload, app.application_id, "approved")

    def test_get_creator_applications_all(self):
        self.auth.submit_creator_application(self.uid1, "reason1")
        self.auth.submit_creator_application(self.uid2, "reason2")
        result = self.auth.get_creator_applications()
        self.assertEqual(result["total"], 2)
        self.assertEqual(len(result["items"]), 2)

    def test_get_creator_applications_filter_by_status(self):
        app1 = self.auth.submit_creator_application(self.uid1, "reason1")
        self.auth.submit_creator_application(self.uid2, "reason2")
        self.auth.review_creator_application(self.admin_payload, app1.application_id, "approved")
        pending = self.auth.get_creator_applications(status="pending")
        self.assertEqual(pending["total"], 1)
        approved = self.auth.get_creator_applications(status="approved")
        self.assertEqual(approved["total"], 1)

    def test_get_my_creator_application_none(self):
        result = self.auth.get_my_creator_application(self.uid1)
        self.assertIsNone(result)

    def test_get_my_creator_application_returns_latest(self):
        app = self.auth.submit_creator_application(self.uid1, "reason")
        result = self.auth.get_my_creator_application(self.uid1)
        self.assertIsNotNone(result)
        self.assertEqual(result.application_id, app.application_id)

    def test_application_to_dict(self):
        app = self.auth.submit_creator_application(self.uid1, "reason", "https://port.io")
        d = app.to_dict()
        self.assertIn("application_id", d)
        self.assertIn("status", d)
        self.assertIn("created_at", d)
        self.assertIsNone(d["reviewed_at"])

    def test_after_rejection_can_reapply(self):
        app = self.auth.submit_creator_application(self.uid1, "first attempt")
        self.auth.review_creator_application(self.admin_payload, app.application_id, "rejected")
        new_app = self.auth.submit_creator_application(self.uid1, "second attempt")
        self.assertEqual(new_app.status, "pending")

    def test_pagination_offset(self):
        self.auth.submit_creator_application(self.uid1, "reason1")
        self.auth.submit_creator_application(self.uid2, "reason2")
        page1 = self.auth.get_creator_applications(limit=1, offset=0)
        page2 = self.auth.get_creator_applications(limit=1, offset=1)
        self.assertEqual(page1["total"], 2)
        self.assertTrue(page1["has_more"])
        self.assertFalse(page2["has_more"])
        ids = {page1["items"][0]["application_id"], page2["items"][0]["application_id"]}
        self.assertEqual(len(ids), 2)


class TestTagFollowing(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager()
        self.auth.register("alice", "alice@x.com", "Alice123!")
        self.uid = self.auth.store.get_by_username("alice").user_id

    def test_follow_tag_returns_list(self):
        tags = self.auth.follow_tag(self.uid, "fantasy")
        self.assertIn("fantasy", tags)

    def test_follow_tag_normalised_lowercase(self):
        tags = self.auth.follow_tag(self.uid, "FANTASY")
        self.assertIn("fantasy", tags)

    def test_follow_tag_deduplicated(self):
        self.auth.follow_tag(self.uid, "vrc")
        tags = self.auth.follow_tag(self.uid, "vrc")
        self.assertEqual(tags.count("vrc"), 1)

    def test_follow_empty_tag_raises(self):
        with self.assertRaises(ValueError):
            self.auth.follow_tag(self.uid, "   ")

    def test_unfollow_tag_removes_it(self):
        self.auth.follow_tag(self.uid, "mecha")
        tags = self.auth.unfollow_tag(self.uid, "mecha")
        self.assertNotIn("mecha", tags)

    def test_unfollow_nonexistent_tag_is_noop(self):
        tags = self.auth.unfollow_tag(self.uid, "nonexistent")
        self.assertIsInstance(tags, list)

    def test_get_followed_tags_empty_initially(self):
        tags = self.auth.get_followed_tags(self.uid)
        self.assertEqual(tags, [])

    def test_get_followed_tags_returns_all(self):
        self.auth.follow_tag(self.uid, "fantasy")
        self.auth.follow_tag(self.uid, "mecha")
        tags = self.auth.get_followed_tags(self.uid)
        self.assertIn("fantasy", tags)
        self.assertIn("mecha", tags)

    def test_follow_tag_unknown_user_raises(self):
        with self.assertRaises(AuthError):
            self.auth.follow_tag("no-such-id", "fantasy")

    def test_get_followed_tags_unknown_user_raises(self):
        with self.assertRaises(AuthError):
            self.auth.get_followed_tags("no-such-id")

    def test_get_public_profile_includes_follower_count(self):
        self.auth.register("bob", "bob@x.com", "Bob1234!")
        bob_id = self.auth.store.get_by_username("bob").user_id
        self.auth.follow(bob_id, self.uid)
        profile = self.auth.get_public_profile(self.uid)
        self.assertIn("followers_count", profile)
        self.assertEqual(profile["followers_count"], 1)

    def test_get_public_profile_inactive_user_raises(self):
        user = self.auth.store.get_by_id(self.uid)
        user.is_active = False
        with self.assertRaises(AuthError):
            self.auth.get_public_profile(self.uid)

    def test_get_public_profile_unknown_user_raises(self):
        with self.assertRaises(AuthError):
            self.auth.get_public_profile("no-such-id")


class TestUserBan(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager(UserStore())
        self.auth.register("alice", "alice@x.com", "Alice123!")
        self.alice_id = self.auth.store.get_by_username("alice").user_id
        self.auth.register("admin", "admin@x.com", "Admin123!")
        admin_user = self.auth.store.get_by_username("admin")
        admin_user.role = "admin"
        self.admin_id = admin_user.user_id
        self.admin_payload = {"sub": self.admin_id, "role": "admin"}

    def test_ban_user_sets_flags(self):
        user = self.auth.ban_user(self.admin_payload, self.alice_id, "spam")
        self.assertTrue(user.is_banned)
        self.assertEqual(user.ban_reason, "spam")
        self.assertIsNotNone(user.banned_at)
        self.assertEqual(user.banned_by, self.admin_id)

    def test_ban_user_non_admin_raises(self):
        user_payload = {"sub": self.alice_id, "role": "user"}
        with self.assertRaises(AuthError):
            self.auth.ban_user(user_payload, self.alice_id, "test")

    def test_ban_self_raises(self):
        with self.assertRaises(AuthError) as ctx:
            self.auth.ban_user(self.admin_payload, self.admin_id)
        self.assertEqual(ctx.exception.code, "forbidden")

    def test_ban_unknown_user_raises(self):
        with self.assertRaises(AuthError) as ctx:
            self.auth.ban_user(self.admin_payload, "no-such-id")
        self.assertEqual(ctx.exception.code, "not_found")

    def test_banned_user_cannot_login(self):
        self.auth.ban_user(self.admin_payload, self.alice_id, "test ban")
        with self.assertRaises(AuthError) as ctx:
            self.auth.login("alice", "Alice123!")
        self.assertEqual(ctx.exception.code, "account_banned")

    def test_unban_user_clears_flags(self):
        self.auth.ban_user(self.admin_payload, self.alice_id)
        user = self.auth.unban_user(self.admin_payload, self.alice_id)
        self.assertFalse(user.is_banned)
        self.assertEqual(user.ban_reason, "")
        self.assertIsNone(user.banned_at)

    def test_unban_unknown_user_raises(self):
        with self.assertRaises(AuthError) as ctx:
            self.auth.unban_user(self.admin_payload, "no-such-id")
        self.assertEqual(ctx.exception.code, "not_found")

    def test_unban_non_admin_raises(self):
        self.auth.ban_user(self.admin_payload, self.alice_id)
        user_payload = {"sub": self.alice_id, "role": "user"}
        with self.assertRaises(AuthError):
            self.auth.unban_user(user_payload, self.alice_id)

    def test_unbanned_user_can_login_again(self):
        self.auth.ban_user(self.admin_payload, self.alice_id)
        self.auth.unban_user(self.admin_payload, self.alice_id)
        tokens = self.auth.login("alice", "Alice123!")
        self.assertIsNotNone(tokens.access_token)

    def test_get_banned_users_lists_banned(self):
        self.auth.ban_user(self.admin_payload, self.alice_id, "spam")
        result = self.auth.get_banned_users(self.admin_payload)
        self.assertEqual(result["total"], 1)
        item = result["items"][0]
        self.assertEqual(item["user_id"], self.alice_id)
        self.assertTrue(item["is_banned"])

    def test_get_banned_users_empty_when_none(self):
        result = self.auth.get_banned_users(self.admin_payload)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])

    def test_get_banned_users_non_admin_raises(self):
        user_payload = {"sub": self.alice_id, "role": "user"}
        with self.assertRaises(AuthError):
            self.auth.get_banned_users(user_payload)

    def test_get_banned_users_pagination(self):
        for i in range(3):
            self.auth.register(f"u{i}", f"u{i}@x.com", "User1234!")
            uid = self.auth.store.get_by_username(f"u{i}").user_id
            self.auth.ban_user(self.admin_payload, uid)
        result = self.auth.get_banned_users(self.admin_payload, limit=2, offset=0)
        self.assertEqual(result["total"], 3)
        self.assertEqual(len(result["items"]), 2)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 2)

    def test_ban_reason_truncated_at_500(self):
        long_reason = "x" * 600
        user = self.auth.ban_user(self.admin_payload, self.alice_id, long_reason)
        self.assertEqual(len(user.ban_reason), 500)

    def test_ban_reason_stripped(self):
        user = self.auth.ban_user(self.admin_payload, self.alice_id, "  spam  ")
        self.assertEqual(user.ban_reason, "spam")


# ---------------------------------------------------------------------------
# UserStore registration race (TOCTOU)
# ---------------------------------------------------------------------------

class TestUserStoreRegistrationRace(unittest.TestCase):
    """Concurrent registrations with the same username must produce exactly one account."""

    def test_concurrent_same_username_only_one_succeeds(self):
        import threading
        store = UserStore()
        successes = []
        errors = []

        def register():
            try:
                store.create_user("alice", "alice@test.com", "pw123456")
                successes.append(1)
            except ValueError:
                errors.append(1)

        threads = [threading.Thread(target=register) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(successes), 1, "Exactly one registration must succeed")
        self.assertEqual(len(errors), 9, "All other concurrent attempts must fail")
        self.assertEqual(len(store.list_users()), 1)

    def test_concurrent_same_email_only_one_succeeds(self):
        import threading
        store = UserStore()
        successes = []

        def register(i):
            try:
                store.create_user(f"user{i}", "shared@test.com", "pw123456")
                successes.append(1)
            except ValueError:
                pass

        threads = [threading.Thread(target=register, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(store.list_users()), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
