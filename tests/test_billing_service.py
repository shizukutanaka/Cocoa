"""Tests for billing_service — BillingConfig, BillingStorage, BillingEventLog, StripeBillingService."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))
from billing_service import (
    BillingConfig,
    BillingError,
    BillingEventLog,
    BillingStorage,
    PriceTier,
    StripeBillingService,
)


class TestPriceTier(unittest.TestCase):

    def test_basic_creation(self):
        tier = PriceTier(key="basic", price_id="price_123", description="Basic plan")
        self.assertEqual(tier.key, "basic")
        self.assertEqual(tier.price_id, "price_123")


class TestBillingConfig(unittest.TestCase):

    def test_from_dict_minimal(self):
        cfg = BillingConfig.from_dict({"billing": {}})
        self.assertFalse(cfg.enabled)

    def test_from_dict_enabled(self):
        cfg = BillingConfig.from_dict({"billing": {"enabled": True}})
        self.assertTrue(cfg.enabled)

    def test_from_dict_defaults(self):
        cfg = BillingConfig.from_dict({})
        self.assertFalse(cfg.enabled)

    def test_resolve_price_unknown_tier_raises(self):
        cfg = BillingConfig.from_dict({})
        with self.assertRaises(BillingError):
            cfg.resolve_price("nonexistent")

    def test_webhook_secret_default_none(self):
        cfg = BillingConfig.from_dict({})
        self.assertIsNone(cfg.webhook_secret_env)


class TestBillingStorage(unittest.TestCase):

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmpfile.close()
        self.storage = BillingStorage(storage_path=Path(self.tmpfile.name))

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_upsert_and_get_by_user(self):
        self.storage.upsert_subscription("user_1", {"user_id": "user_1", "plan": "pro"})
        record = self.storage.get_by_user("user_1")
        self.assertIsNotNone(record)
        self.assertEqual(record["plan"], "pro")

    def test_get_by_user_missing_returns_none(self):
        result = self.storage.get_by_user("nonexistent_user")
        self.assertIsNone(result)

    def test_all_records_returns_dict(self):
        self.storage.upsert_subscription("k1", {"user_id": "u1"})
        self.storage.upsert_subscription("k2", {"user_id": "u2"})
        records = self.storage.all_records()
        self.assertIsInstance(records, dict)
        self.assertEqual(len(records), 2)

    def test_overwrite_subscription(self):
        self.storage.upsert_subscription("user_1", {"user_id": "user_1", "plan": "free"})
        self.storage.upsert_subscription("user_1", {"user_id": "user_1", "plan": "pro"})
        record = self.storage.get_by_user("user_1")
        self.assertEqual(record["plan"], "pro")


class TestBillingEventLog(unittest.TestCase):

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmpfile.close()
        self.log = BillingEventLog(path=Path(self.tmpfile.name))

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_has_returns_false_for_new_event(self):
        self.assertFalse(self.log.has("evt_new_123"))

    def test_record_and_has(self):
        self.log.record("evt_abc", "invoice.paid")
        self.assertTrue(self.log.has("evt_abc"))

    def test_duplicate_record_no_error(self):
        self.log.record("evt_dup", "charge.succeeded")
        self.log.record("evt_dup", "charge.succeeded")
        self.assertTrue(self.log.has("evt_dup"))


class TestStripeBillingServiceInit(unittest.TestCase):

    def test_raises_without_stripe(self):
        """StripeBillingService raises BillingError when stripe not installed."""
        from billing_service import STRIPE_AVAILABLE
        if STRIPE_AVAILABLE:
            self.skipTest("stripe is installed; skipping unavailability test")
        config = BillingConfig.from_dict({"billing": {"enabled": True}})
        with self.assertRaises(BillingError):
            StripeBillingService(config=config)

    def test_raises_without_api_key(self):
        """StripeBillingService raises BillingError when STRIPE_API_KEY not set."""
        from billing_service import STRIPE_AVAILABLE
        if not STRIPE_AVAILABLE:
            self.skipTest("stripe not installed")
        import os
        os.environ.pop("STRIPE_API_KEY", None)
        config = BillingConfig.from_dict({"billing": {"enabled": True}})
        with self.assertRaises(BillingError):
            StripeBillingService(config=config)


class TestBillingEventLogTimestampParsing(unittest.TestCase):
    """BillingEventLog must parse 'Z'-suffixed timestamps as timezone-aware.

    Bug: _parse_ts used raw.replace('Z', '') which strips the tzinfo,
    yielding a naive datetime. Later code compares it against
    datetime.now(timezone.utc) — an aware datetime — which raises
    `TypeError: can't compare offset-naive and offset-aware datetimes`.

    Qiita/Zenn anti-pattern: datetime.fromisoformat without preserving
    tz info, then comparing against an aware datetime.
    """

    def test_parse_ts_keeps_tzinfo_for_z_suffix(self):
        from billing_service import BillingEventLog
        result = BillingEventLog._parse_ts("2024-06-01T12:00:00Z")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.tzinfo,
            "Z-suffixed timestamp must produce a timezone-aware datetime")

    def test_parse_ts_can_be_compared_to_aware_now(self):
        """Regression: the failure mode is a TypeError when comparing."""
        from datetime import datetime, timezone
        from billing_service import BillingEventLog
        parsed = BillingEventLog._parse_ts("2024-01-01T00:00:00Z")
        now = datetime.now(timezone.utc)
        # Before the fix, this comparison raised TypeError.
        self.assertTrue(parsed < now)

    def test_parse_ts_returns_none_for_invalid(self):
        from billing_service import BillingEventLog
        self.assertIsNone(BillingEventLog._parse_ts("not-a-date"))
        self.assertIsNone(BillingEventLog._parse_ts(None))
        self.assertIsNone(BillingEventLog._parse_ts(""))

    def test_parse_ts_keeps_tzinfo_for_explicit_offset(self):
        from billing_service import BillingEventLog
        result = BillingEventLog._parse_ts("2024-06-01T12:00:00+09:00")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.tzinfo)
