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
import unittest.mock
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


class TestSingleWriterLock(unittest.TestCase):
    """Multi-worker against one state directory must be refused, not tolerated.

    The stores are per-process dicts, so `uvicorn --workers 2` is not "slower
    but fine": measured against the real API, 9 of 12 registrations succeeded
    but only 3 of those accounts could log in, because each lived in one
    worker's memory. With durability on, each worker also autosaves the whole
    store over the same file, so the last writer erases the others' work.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        self.addCleanup(snapshot.release_single_writer_lock)

    def test_second_holder_is_refused(self):
        snapshot.acquire_single_writer_lock(self.dir)
        # A second acquisition from another process must fail. Same-process
        # flock re-acquisition succeeds by design, so use a real subprocess.
        import subprocess, sys as _sys, textwrap
        code = textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {str(Path(__file__).resolve().parent.parent / "main")!r})
            import state_snapshot
            try:
                state_snapshot.acquire_single_writer_lock({self.dir!r})
            except state_snapshot.StateDirInUseError:
                sys.exit(42)
            sys.exit(0)
        """)
        result = subprocess.run([_sys.executable, "-c", code], capture_output=True)
        self.assertEqual(result.returncode, 42, "a second process acquired the lock")

    def test_lock_is_reusable_after_release(self):
        # A clean shutdown must not leave the directory permanently claimed.
        snapshot.acquire_single_writer_lock(self.dir)
        snapshot.release_single_writer_lock()
        self.assertIsNotNone(snapshot.acquire_single_writer_lock(self.dir))

    def test_lock_file_is_not_group_or_world_readable(self):
        import os
        snapshot.acquire_single_writer_lock(self.dir)
        mode = os.stat(os.path.join(self.dir, snapshot.LOCK_FILENAME)).st_mode & 0o777
        self.assertEqual(mode & 0o077, 0)


class TestSnapshotIsSafeUnderLiveTraffic(unittest.TestCase):
    """Snapshotting must not race the requests it is snapshotting.

    Encoding walks the store's dicts, so without holding the store's lock a
    concurrent write throws "dictionary changed size during iteration".
    Measured before the fix: 60 of 60 snapshot attempts failed while the store
    was being written. Because the autosave swallows errors, durability would
    have looked enabled while silently never writing -- the operator would
    discover it only after a restart lost everything.
    """

    def test_snapshot_survives_concurrent_writes(self):
        import threading
        store = market.MarketplaceStore()
        for i in range(50):
            store.publish(
                avatar_id=f"a{i}", owner_id="o", owner_username="o", name=f"n{i}",
                description="d", tags=["t"], category="other", parameters={"p": i},
            )

        stop = threading.Event()
        failures = []

        def writer():
            i = 1000
            while not stop.is_set():
                try:
                    store.publish(
                        avatar_id=f"a{i}", owner_id="o", owner_username="o", name=f"n{i}",
                        description="d", tags=["t"], category="other", parameters={"p": i},
                    )
                    store.add_credits(f"u{i}", 1)
                except Exception as e:  # pragma: no cover
                    failures.append(e)
                i += 1

        thread = threading.Thread(target=writer, daemon=True)
        thread.start()
        try:
            for _ in range(25):
                codec.snapshot_attrs(store)  # must not raise
        finally:
            stop.set()
            thread.join(timeout=5)
        self.assertEqual(failures, [])

    def test_a_store_without_a_lock_still_snapshots(self):
        # Not every snapshotted object is lock-protected; those must not break.
        class Plain:
            def __init__(self):
                self.data = {"a": 1}

        self.assertEqual(codec.snapshot_attrs(Plain()), {"data": {"a": 1}})


class TestDownloadLogIsBounded(unittest.TestCase):
    """Unbounded history became an operational cliff once snapshots existed.

    The download log grew forever, one entry per download, and the whole thing
    is re-encoded under the store lock every 30 seconds. Measured: 100k entries
    = 314ms of blocked requests and a 10MB snapshot; 500k = 2.5s and 49MB. It
    is now capped the same way cart_manager caps orders per user and
    user_notifications caps the queue.
    """

    def test_log_is_capped_and_drops_the_oldest(self):
        import importlib
        import os
        with unittest.mock.patch.dict(os.environ, {"MAX_DOWNLOAD_LOG": "25"}):
            module = importlib.reload(market)
            try:
                store = module.MarketplaceStore()
                listing = store.publish(
                    avatar_id="a", owner_id="o", owner_username="o", name="n",
                    description="d", tags=[], category="other", parameters={"p": 1},
                )
                now = datetime.now(timezone.utc)
                for i in range(60):
                    store._record_download_locked(listing.listing_id, f"u{i}", now)
                self.assertEqual(len(store._download_log), 25)
                # Newest survive, oldest are gone.
                self.assertIn("u59", [row[1] for row in store._download_log])
                self.assertNotIn("u0", [row[1] for row in store._download_log])
                # Ownership is NOT derived from the log, so the trimmed-out
                # buyer keeps their purchase and can still re-download.
                self.assertTrue(store._has_downloaded_locked("u0", listing.listing_id))
            finally:
                importlib.reload(module)


if __name__ == "__main__":
    unittest.main()

class TestModerationHistoryIsBounded(unittest.TestCase):
    """Adjudicated moderation history is capped; open reports never are.

    Items were never removed -- resolving one only flips its status -- so every
    report ever filed accumulated forever, and unlike the download log these are
    FREE for any logged-in user to create. With snapshots the whole queue is
    re-encoded under the store lock every 30s: measured, 100k items cost 1.4s of
    blocked requests and a 51MB snapshot; 300k cost 8s and 154MB.

    The eviction rule is the load-bearing part: dropping an unadjudicated report
    would recreate the #46 dead end (a complaint nobody can act on because it
    silently vanished), so only terminal items are ever discarded.
    """

    def _queue(self, cap):
        import importlib
        import os
        import moderation_queue
        with unittest.mock.patch.dict(os.environ, {"MAX_MODERATION_HISTORY": str(cap)}):
            module = importlib.reload(moderation_queue)
        self.addCleanup(lambda: importlib.reload(module))
        return module.ModerationQueue()

    def test_resolved_history_stays_bounded_and_evicts_oldest_first(self):
        # The guarantee is a high-water mark of cap + slack, not an exact cap:
        # the scan is amortised (once per slack additions) so it is not paid on
        # every enqueue. What matters is that history does not grow with input.
        q = self._queue(20)
        for i in range(60):
            item = q.enqueue(kind="listing_report", source_id=f"s{i}", subject_id="l",
                             reporter_id="u", reason="spam")
            q.update_status(item.item_id, "resolved")
        retained = [i for i in q._items.values() if i.status == "resolved"]
        self.assertLessEqual(len(retained), 22, "history is not bounded")

        # Filing three times as many must not grow it further.
        for i in range(60, 240):
            item = q.enqueue(kind="listing_report", source_id=f"s{i}", subject_id="l",
                             reporter_id="u", reason="spam")
            q.update_status(item.item_id, "resolved")
        grown = [i for i in q._items.values() if i.status == "resolved"]
        self.assertLessEqual(len(grown), 22, "history grew with input")

        sources = {i.source_id for i in grown}
        self.assertIn("s239", sources)   # newest kept
        self.assertNotIn("s0", sources)  # oldest evicted

    def test_open_reports_are_never_evicted(self):
        # The invariant that matters: an unadjudicated complaint must not vanish.
        q = self._queue(5)
        for i in range(40):
            item = q.enqueue(kind="listing_report", source_id=f"done{i}", subject_id="l",
                             reporter_id="u", reason="spam")
            q.update_status(item.item_id, "dismissed")
        for i in range(25):
            q.enqueue(kind="listing_report", source_id=f"open{i}", subject_id="l",
                      reporter_id="u", reason="spam")
        open_items = [i for i in q._items.values() if i.status in ("pending", "in_review")]
        self.assertEqual(len(open_items), 25, "an unadjudicated report was silently dropped")

    def test_a_queue_of_only_open_items_is_never_trimmed(self):
        # Exceeding the cap while everything is still open is an operational
        # emergency; it must stay visible rather than be trimmed away.
        q = self._queue(3)
        for i in range(30):
            q.enqueue(kind="listing_report", source_id=f"s{i}", subject_id="l",
                      reporter_id="u", reason="spam")
        self.assertEqual(len(q._items), 30)

    def test_evicting_an_item_does_not_block_a_later_report_for_that_source(self):
        q = self._queue(1)
        first = q.enqueue(kind="listing_report", source_id="same", subject_id="l",
                          reporter_id="u", reason="spam")
        q.update_status(first.item_id, "resolved")
        for i in range(5):
            later = q.enqueue(kind="listing_report", source_id=f"other{i}", subject_id="l",
                              reporter_id="u", reason="spam")
            q.update_status(later.item_id, "resolved")
        # "same" was evicted; a fresh complaint about it must still queue.
        again = q.enqueue(kind="listing_report", source_id="same", subject_id="l",
                          reporter_id="u2", reason="spam")
        self.assertIn(again.item_id, q._items)
        self.assertIn(again.status, ("pending", "in_review"))


class TestVersionPayloadsAreBounded(unittest.TestCase):
    """publish_version bypassed the limits publish enforces (audit #84).

    publish caps parameters at 500 keys / 64KB. publish_version applied neither,
    and it writes the payload onto the LIVE listing as well as into history, so
    the identical payload publish rejected could be stored twice over through
    the versions endpoint. Measured against a live server: a normal account
    pushed ~55MB into one listing in 1.1 seconds, and with snapshots every byte
    is re-encoded under the store lock every 30 seconds.

    Root cause was duplicated validation that drifted, so the bounds now live in
    one helper both paths call.
    """

    def _store(self, max_versions=None):
        import importlib
        import os
        import avatar_marketplace
        env = {"MAX_VERSIONS_PER_LISTING": str(max_versions)} if max_versions else {}
        with unittest.mock.patch.dict(os.environ, env):
            module = importlib.reload(avatar_marketplace)
        self.addCleanup(lambda: importlib.reload(module))
        return module

    def _listing(self, module, store):
        return store.publish(
            avatar_id="a", owner_id="o", owner_username="o", name="n",
            description="d", tags=[], category="other", parameters={"p": 1},
        )

    def test_publish_version_rejects_what_publish_rejects(self):
        module = self._store()
        store = module.MarketplaceStore()
        listing = self._listing(module, store)
        oversized = {f"k{i}": "x" * 500 for i in range(4000)}
        with self.assertRaises(ValueError):
            store.publish(
                avatar_id="b", owner_id="o", owner_username="o", name="n2",
                description="d", tags=[], category="other", parameters=oversized,
            )
        with self.assertRaises(ValueError):
            store.publish_version(listing.listing_id, "o", changelog="big",
                                  parameters=oversized)

    def test_a_rejected_version_does_not_touch_the_live_listing(self):
        # publish_version writes onto the listing too, so a bypass poisoned the
        # live record and not just history.
        module = self._store()
        store = module.MarketplaceStore()
        listing = self._listing(module, store)
        with self.assertRaises(ValueError):
            store.publish_version(listing.listing_id, "o", changelog="big",
                                  parameters={f"k{i}": "x" * 500 for i in range(4000)})
        current = store.get_listing(listing.listing_id)
        self.assertEqual(current.parameters, {"p": 1})
        self.assertEqual(current.current_version, 1)

    def test_version_history_is_capped_keeping_the_newest(self):
        module = self._store(max_versions=10)
        store = module.MarketplaceStore()
        listing = self._listing(module, store)
        for i in range(40):
            store.publish_version(listing.listing_id, "o", changelog=f"v{i}",
                                  parameters={"p": i})
        kept = store._versions[listing.listing_id]
        self.assertEqual(len(kept), 10)
        self.assertEqual(kept[-1].changelog, "v39")
        # Trimming history must not rewind the listing's version counter.
        self.assertEqual(store.get_listing(listing.listing_id).current_version, 41)

    def test_ordinary_versions_still_work(self):
        module = self._store()
        store = module.MarketplaceStore()
        listing = self._listing(module, store)
        version = store.publish_version(listing.listing_id, "o", changelog="tweak",
                                        parameters={"Hair": 0.5})
        self.assertEqual(version.changelog, "tweak")
        self.assertEqual(store.get_listing(listing.listing_id).parameters, {"Hair": 0.5})


class TestRemainingAppendOnlyLogsAreBounded(unittest.TestCase):
    """Finishing the growth sweep honestly (audit #85).

    #84 claimed none of the four append-only structures in avatar_marketplace
    had a cap. That was wrong about one of them: _review_replies has always been
    bounded by _MAX_REPLIES_PER_REVIEW (a class attribute, which is why a grep
    for module-level _MAX constants missed it). Of the genuinely unbounded
    remainder:

      _price_history  only records real price changes, but a seller alternating
                      10 -> 11 -> 10 produces real changes forever, so the only
                      friction was the request rate limit
      _tips           every tip costs at least a credit, so this one has real
                      economic friction the other logs lack -- but it still only
                      grew, and it is snapshotted like everything else

    Trimming the tip log must never touch the money: balances and the ledger are
    separate structures, and the ledger is what a restored snapshot is verified
    against (#71).
    """

    def _module(self, **env):
        import importlib
        import os
        import avatar_marketplace
        with unittest.mock.patch.dict(os.environ, {k: str(v) for k, v in env.items()}):
            module = importlib.reload(avatar_marketplace)
        self.addCleanup(lambda: importlib.reload(module))
        return module

    def test_price_history_is_bounded_keeping_recent_movement(self):
        module = self._module(MAX_PRICE_HISTORY=10)
        store = module.MarketplaceStore()
        listing = store.publish(
            avatar_id="a", owner_id="o", owner_username="o", name="n", description="d",
            tags=[], category="other", parameters={"p": 1}, price_credits=10, is_free=False,
        )
        for i in range(80):
            store.update_listing(listing.listing_id, "o", price_credits=10 + (i % 2))
        history = store._price_history[listing.listing_id]
        self.assertLessEqual(len(history), 10)
        # Buyers are shown recent movement, so the newest entry must survive.
        self.assertEqual(history[-1]["price_credits"], 10 + (79 % 2))

    def test_trimming_the_tip_log_never_moves_money(self):
        module = self._module(MAX_TIPS=5)
        store = module.MarketplaceStore()
        store.add_credits("sender", 1000)
        for i in range(40):
            store.send_tip("sender", "snd", f"r{i % 3}", 1)

        self.assertLessEqual(len(store._tips), 5, "tip log is not bounded")
        # The log is a display record; the money lives elsewhere and is intact.
        self.assertEqual(store.get_balance("sender"), 960)
        self.assertEqual(sum(store.get_balance(f"r{i}") for i in range(3)), 40)
        discrepancies, _ = store._ledger_discrepancies(store._credits, store._credit_ledger)
        self.assertEqual(discrepancies, [], "trimming the tip log corrupted the ledger")

    def test_review_replies_were_already_bounded(self):
        # Pinning the correction: this cap predates the sweep.
        module = self._module()
        self.assertLessEqual(module.MarketplaceStore._MAX_REPLIES_PER_REVIEW, 1000)
        self.assertGreater(module.MarketplaceStore._MAX_REPLIES_PER_REVIEW, 0)
