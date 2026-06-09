"""Acceptance tests for logging_config improvements.

Spec: docs/SPEC_LOGGING_CONFIG.md (REQ-LC-01..04)
Runnable without pytest:  python3 -m unittest tests.test_logging_config -v
"""
import json
import logging
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "main")):
    if p not in sys.path:
        sys.path.insert(0, p)

import logging_config as lc  # noqa: E402
from logging_config import (  # noqa: E402
    _validate_level, JSONFormatter, CorrelationIdFilter,
    LogContext, set_correlation_id, get_correlation_id,
)


class TestValidateLevel(unittest.TestCase):
    def test_valid_levels_uppercase(self):
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            numeric = _validate_level(level)
            self.assertEqual(numeric, getattr(logging, level))

    def test_valid_levels_lowercase(self):
        self.assertEqual(_validate_level("debug"), logging.DEBUG)
        self.assertEqual(_validate_level("warning"), logging.WARNING)

    def test_valid_levels_mixed_case(self):
        self.assertEqual(_validate_level("Debug"), logging.DEBUG)
        self.assertEqual(_validate_level("Warning"), logging.WARNING)

    def test_invalid_level_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            _validate_level("VERBOSE")
        self.assertIn("VERBOSE", str(ctx.exception))

    def test_invalid_level_empty_raises(self):
        with self.assertRaises(ValueError):
            _validate_level("")

    def test_invalid_level_numeric_string_raises(self):
        with self.assertRaises(ValueError):
            _validate_level("10")


class TestJSONFormatterTimestamp(unittest.TestCase):
    def setUp(self):
        self.formatter = JSONFormatter()
        self.filter = CorrelationIdFilter()

    def _make_record(self, msg="test"):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=1,
            msg=msg, args=(), exc_info=None
        )
        self.filter.filter(record)
        return record

    def test_format_is_valid_json(self):
        record = self._make_record()
        output = self.formatter.format(record)
        data = json.loads(output)
        self.assertIsInstance(data, dict)

    def test_timestamp_field_present(self):
        record = self._make_record()
        output = self.formatter.format(record)
        data = json.loads(output)
        self.assertIn("timestamp", data)

    def test_timestamp_is_utc(self):
        record = self._make_record()
        output = self.formatter.format(record)
        data = json.loads(output)
        ts = data["timestamp"]
        # ISO-8601 with UTC offset: ends in +00:00 or Z
        self.assertTrue(
            ts.endswith("+00:00") or ts.endswith("Z"),
            f"Timestamp {ts!r} does not indicate UTC"
        )

    def test_format_contains_message(self):
        record = self._make_record("hello world")
        output = self.formatter.format(record)
        data = json.loads(output)
        self.assertEqual(data["message"], "hello world")

    def test_format_contains_level(self):
        record = self._make_record()
        output = self.formatter.format(record)
        data = json.loads(output)
        self.assertEqual(data["level"], "INFO")

    def test_format_contains_correlation_id(self):
        lc.set_correlation_id("test-corr-001")
        record = self._make_record()
        output = self.formatter.format(record)
        data = json.loads(output)
        self.assertEqual(data["correlation_id"], "test-corr-001")
        lc.set_correlation_id(None)


class TestConfigureLogging(unittest.TestCase):
    def test_invalid_level_raises(self):
        with self.assertRaises(ValueError):
            lc.configure_logging(level="INVALID")

    def test_valid_level_does_not_raise(self):
        # Should not raise; call is side-effectful (modifies root logger)
        lc.configure_logging(level="WARNING", json_format=False)

    def test_configure_sets_root_level(self):
        lc.configure_logging(level="ERROR", json_format=False)
        root = logging.getLogger()
        self.assertEqual(root.level, logging.ERROR)


class TestGetLogger(unittest.TestCase):
    def test_returns_logger(self):
        logger = lc.get_logger("test.module")
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "test.module")

    def test_cached_logger(self):
        l1 = lc.get_logger("test.cached")
        l2 = lc.get_logger("test.cached")
        self.assertIs(l1, l2)


class TestSetCorrelationId(unittest.TestCase):
    def tearDown(self):
        set_correlation_id(None)

    def test_set_and_get(self):
        set_correlation_id("req-abc-123")
        self.assertEqual(get_correlation_id(), "req-abc-123")

    def test_overwrite(self):
        set_correlation_id("first")
        set_correlation_id("second")
        self.assertEqual(get_correlation_id(), "second")

    def test_set_none_clears(self):
        set_correlation_id("some-id")
        set_correlation_id(None)
        self.assertIsNone(get_correlation_id())


class TestLogContext(unittest.TestCase):

    def _make_logger(self):
        logger = logging.getLogger(f"test_ctx_{id(self)}")
        logger.setLevel(logging.DEBUG)
        return logger

    def test_enter_returns_self(self):
        logger = self._make_logger()
        ctx = LogContext(logger, "operation")
        result = ctx.__enter__()
        self.assertIs(result, ctx)

    def test_exit_success_returns_false(self):
        logger = self._make_logger()
        ctx = LogContext(logger, "op")
        ctx.__enter__()
        result = ctx.__exit__(None, None, None)
        self.assertFalse(result)

    def test_exit_exception_returns_false(self):
        logger = self._make_logger()
        ctx = LogContext(logger, "op")
        ctx.__enter__()
        result = ctx.__exit__(ValueError, ValueError("oops"), None)
        self.assertFalse(result)

    def test_context_manager_protocol(self):
        logger = self._make_logger()
        with LogContext(logger, "test-op") as ctx:
            self.assertIsInstance(ctx, LogContext)

    def test_exception_propagates(self):
        logger = self._make_logger()
        with self.assertRaises(RuntimeError):
            with LogContext(logger, "failing-op"):
                raise RuntimeError("intentional")


if __name__ == "__main__":
    unittest.main(verbosity=2)
