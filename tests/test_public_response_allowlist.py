"""Public responses expose an explicit, pinned set of fields (audit #107).

OWASP API3:2023 (Broken Object Property Level Authorization) is the class where
an API returns more of an object than the caller may see -- typically because a
serializer was written as "dump the record" and a sensitive field was added to
the record later. Measured against a running server first: nothing sensitive is
exposed today (no email, password hash, pw_version, ban notes, or listing
parameter VALUES). This pins that state so it takes a deliberate edit here, in
review, to widen it -- the #101 lesson: a class is closed by the mechanism that
fails on the N+1th field, not by having checked N.
"""
import sys
import unittest
from dataclasses import fields
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "main"))

from auth_manager import UserRecord  # noqa: E402
from avatar_marketplace import MarketplaceStore  # noqa: E402

PUBLIC_PROFILE_FIELDS = {
    "user_id", "username", "display_name", "bio", "avatar_url", "website_url",
    "social_links", "role", "is_email_verified", "is_creator_verified", "created_at",
}

# Fields that must never appear in any public serialization of a user.
NEVER_PUBLIC = {
    "email", "password_hash", "pw_version", "failed_attempts", "locked_until",
    "last_login", "bookmarks", "following", "followed_tags", "is_banned",
    "ban_reason", "banned_at", "banned_by", "is_active",
}


class TestPublicProfile(unittest.TestCase):
    def _record(self):
        return UserRecord(
            user_id="u1", username="alice", email="alice-secret@example.com",
            password_hash="HASH-SENTINEL", ban_reason="BAN-SENTINEL", banned_by="admin-x",
            bookmarks=["b1"], following=["u2"], followed_tags=["t"], pw_version=7,
        )

    def test_exact_field_set_is_pinned(self):
        self.assertEqual(set(self._record().public_profile()), PUBLIC_PROFILE_FIELDS)

    def test_private_fields_never_appear(self):
        self.assertFalse(set(self._record().public_profile()) & NEVER_PUBLIC)

    def test_no_private_value_leaks_under_any_key(self):
        blob = repr(self._record().public_profile())
        for secret in ("alice-secret@example.com", "HASH-SENTINEL", "BAN-SENTINEL", "admin-x"):
            self.assertNotIn(secret, blob)

    def test_every_record_field_is_classified(self):
        # A new UserRecord field must be consciously placed in one of the two
        # sets above; otherwise it silently defaults to "not reviewed".
        classified = PUBLIC_PROFILE_FIELDS | NEVER_PUBLIC
        unclassified = {f.name for f in fields(UserRecord)} - classified
        self.assertEqual(unclassified, set(),
                         f"classify these UserRecord fields as public or private: {sorted(unclassified)}")


class TestPublicListing(unittest.TestCase):
    def test_listing_parameter_values_are_not_exposed(self):
        # Parameter values are what a buyer pays for; the listing payload shows
        # only the count and a sample of key NAMES until purchase.
        store = MarketplaceStore()
        lst = store.publish(avatar_id="a1", owner_id="u1", owner_username="alice", name="n",
                            description="d", tags=["t"], category="c",
                            parameters={"Hair": "VALUE-SENTINEL"})
        payload = lst.to_dict()
        self.assertNotIn("parameters", payload)
        self.assertNotIn("VALUE-SENTINEL", repr(payload))
        self.assertEqual(payload["parameter_count"], 1)


if __name__ == "__main__":
    unittest.main()
