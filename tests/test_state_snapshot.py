"""Whole-store durability (FEATURE_AUDIT #74).

The reason full persistence stayed deferred for 70+ rounds was that every
store's to_dict() is a lossy presentation serializer -- restoring from one
would silently destroy data. These tests pin the property that made the
migration safe: the codec round-trips the LIVE objects exactly, including the
fields to_dict() drops and the JSON-hostile shapes (sets, tuple dict keys,
tuples containing datetimes).
"""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "main"))

import avatar_marketplace as market  # noqa: E402
import state_codec as codec  # noqa: E402
import state_snapshot as snapshot  # noqa: E402
from auth_manager import AuthManager, UserStore  # noqa: E402


class TestStateCodecRoundTrip(unittest.TestCase):
    def setUp(self):
        self.registry = codec.build_registry(market)

    def _round_trip(self, value):
        return codec.decode(json.loads(json.dumps(codec.encode(value))), self.registry)

    def test_datetime_survives_with_timezone(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(self._round_trip(now), now)

    def test_sets_stay_sets(self):
        self.assertEqual(self._round_trip({"a", "b"}), {"a", "b"})

    def test_tuple_dict_keys_survive(self):
        # _purchase_seller is keyed by (buyer_id, listing_id); plain JSON
        # cannot express that at all.
        value = {("buyer", "listing"): "seller"}
        self.assertEqual(self._round_trip(value), value)

    def test_tuples_containing_datetimes_survive(self):
        now = datetime.now(timezone.utc)
        value = [("listing", "buyer", now, 30)]
        self.assertEqual(self._round_trip(value), value)

    def test_set_of_tuples_survives(self):
        value = {("buyer", "listing")}
        self.assertEqual(self._round_trip(value), value)

    def test_unregistered_dataclass_is_refused(self):
        # The security property that lets this replace pickle: decoding can
        # only ever build types the registry names.
        payload = {"__t__": "dc", "n": "os.system", "v": {}}
        with self.assertRaises(codec.StateCodecError):
            codec.decode(payload, self.registry)

    def test_unknown_field_in_snapshot_is_dropped_not_fatal(self):
        # A snapshot written by a build that had an extra field must still load.
        encoded = codec.encode(market.Tip(tip_id="t", sender_id="s", sender_username="s",
                                          recipient_id="r", amount=5, message="m"))
        encoded["v"]["field_from_the_future"] = 1
        self.assertEqual(codec.decode(encoded, self.registry).tip_id, "t")

    def test_locks_are_never_snapshotted(self):
        store = market.MarketplaceStore()
        self.assertNotIn("_lock", codec.snapshot_attrs(store))


class TestWholeStoreDurability(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = str(Path(self._tmp.name) / "state.json")

    def _populated(self):
        mkt = market.MarketplaceStore()
        listing = mkt.publish(
            avatar_id="a1", owner_id="seller", owner_username="sel", name="服",
            description="d", tags=["t"], category="other",
            parameters={"Hair": 0.5, "Eye": 1}, price_credits=30, is_free=False,
        )
        mkt.add_credits("buyer", 500)
        mkt.download(listing.listing_id, "buyer")
        mkt.review(listing.listing_id, "buyer", "b", 5, "great")
        auth = AuthManager(store=UserStore())
        auth.register("alice", "alice@example.com", "Sup3rSecret!")
        return {"marketplace": mkt, "users": auth.store}, listing, auth

    def test_a_purchased_listings_parameters_survive(self):
        # The exact data to_dict() omits -- and the whole reason a to_dict()
        # based migration would have been a data-loss bug.
        stores, listing, _ = self._populated()
        snapshot.save(self.path, stores)

        reborn = {"marketplace": market.MarketplaceStore(), "users": UserStore()}
        snapshot.load(self.path, reborn)
        restored = reborn["marketplace"].get_listing(listing.listing_id)
        self.assertEqual(restored.parameters, {"Hair": 0.5, "Eye": 1})
        self.assertEqual(restored.rating_sum, 5)

    def test_money_ownership_and_accounts_all_survive_together(self):
        stores, listing, auth = self._populated()
        snapshot.save(self.path, stores)

        mkt2, users2 = market.MarketplaceStore(), UserStore()
        snapshot.load(self.path, {"marketplace": mkt2, "users": users2})
        self.assertEqual(mkt2.get_balance("buyer"), 470)
        self.assertEqual(mkt2.get_balance("seller"), 30)
        # Ownership index (a Dict[str, Set[str]]) still answers correctly, so a
        # buyer can re-download what they paid for.
        self.assertTrue(mkt2._has_downloaded_locked("buyer", listing.listing_id))
        # And the account is still there to log in with.
        self.assertIsNotNone(users2.get_by_username("alice"))

    def test_absent_snapshot_is_a_normal_first_run(self):
        result = snapshot.load(self.path, {"marketplace": market.MarketplaceStore()})
        self.assertFalse(result["loaded"])

    def test_version_mismatch_is_refused(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"version": 999, "stores": {}}, f)
        with self.assertRaises(ValueError):
            snapshot.load(self.path, {"marketplace": market.MarketplaceStore()})

    def test_snapshot_is_not_group_or_world_readable(self):
        import os
        stores, _, _ = self._populated()
        snapshot.save(self.path, stores)
        self.assertEqual(os.stat(self.path).st_mode & 0o077, 0)

    def test_state_for_an_absent_subsystem_is_skipped_not_fatal(self):
        # A degraded deployment (#47) must still restore what it does have.
        stores, _, _ = self._populated()
        snapshot.save(self.path, stores)
        mkt2 = market.MarketplaceStore()
        result = snapshot.load(self.path, {"marketplace": mkt2})  # no "users"
        self.assertTrue(result["loaded"])
        self.assertIn("marketplace", result["restored"])


class TestSecuritySensitiveStateSurvives(unittest.TestCase):
    """Persisting accounts while dropping revocations was a security regression.

    With a stable COCOA_JWT_SECRET a token issued before a restart is still
    cryptographically valid afterwards. Before durability existed a restart
    wiped every account, so such a token resolved to nobody; once accounts
    persisted, a token that had been explicitly REVOKED by logout came back to
    life. Persistence is what made it exploitable -- the same way it turned the
    #73 admin demotion into a permanent lockout.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = str(Path(self._tmp.name) / "state.json")

    def test_a_revoked_token_stays_revoked_across_a_restart(self):
        auth = AuthManager(store=UserStore())
        auth.register("alice", "alice@example.com", "Sup3rSecret!")
        tokens = auth.login("alice", "Sup3rSecret!")
        auth.logout(tokens.access_token, tokens.refresh_token)
        snapshot.save(self.path, {"users": auth.store})

        reborn = AuthManager(store=UserStore())
        snapshot.load(self.path, {"users": reborn.store})
        with self.assertRaises(Exception):
            reborn.verify_access_token(tokens.access_token)

    def test_api_keys_survive_a_restart(self):
        # Everything else now persists, so a key that silently stopped working
        # after a deploy would be an incoherent surprise.
        auth = AuthManager(store=UserStore())
        user = auth.register("bob", "bob@example.com", "Sup3rSecret!")
        created = auth.create_api_key(user.user_id, "ci")
        snapshot.save(self.path, {"users": auth.store})

        reborn = AuthManager(store=UserStore())
        snapshot.load(self.path, {"users": reborn.store})
        self.assertIsNotNone(reborn.verify_api_key(created["raw_key"]))

    def test_runtime_limits_are_not_restored_over_live_config(self):
        # Configuration read from the environment must win over a stale
        # snapshot, so those attributes stay excluded.
        from user_notifications import NotificationQueue
        queue = NotificationQueue(max_per_user=5)
        snapshot.save(self.path, {"notifications": queue})
        reborn = NotificationQueue(max_per_user=99)
        snapshot.load(self.path, {"notifications": reborn})
        self.assertEqual(reborn._max, 99)


if __name__ == "__main__":
    unittest.main()