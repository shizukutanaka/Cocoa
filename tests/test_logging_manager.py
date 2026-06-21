"""Tests for LoggingManager and JsonLogFormatter."""
import json
import logging
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))
from logging_manager import JsonLogFormatter, LoggingManager


class TestJsonLogFormatter(unittest.TestCase):

    def setUp(self):
        self.formatter = JsonLogFormatter()

    def _make_record(self, msg="hello", level=logging.INFO):
        return logging.LogRecord(
            name="test", level=level, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None,
        )

    def test_output_is_valid_json(self):
        record = self._make_record()
        output = self.formatter.format(record)
        data = json.loads(output)
        self.assertIsInstance(data, dict)

    def test_output_has_required_keys(self):
        record = self._make_record()
        data = json.loads(self.formatter.format(record))
        for key in ("timestamp", "logger", "level", "message"):
            self.assertIn(key, data)

    def test_timestamp_is_iso_format(self):
        record = self._make_record()
        data = json.loads(self.formatter.format(record))
        ts = data["timestamp"]
        self.assertIn("T", ts)

    def test_timestamp_contains_utc_offset(self):
        record = self._make_record()
        data = json.loads(self.formatter.format(record))
        ts = data["timestamp"]
        self.assertTrue(ts.endswith(("+00:00", "Z")) or "+" in ts or "-" in ts[-6:])

    def test_message_content(self):
        record = self._make_record("test message")
        data = json.loads(self.formatter.format(record))
        self.assertEqual(data["message"], "test message")

    def test_level_name(self):
        record = self._make_record(level=logging.ERROR)
        data = json.loads(self.formatter.format(record))
        self.assertEqual(data["level"], "ERROR")

    def test_non_serializable_extra_does_not_drop_line(self):
        """A non-JSON-serializable value in extra_data must not raise.

        Without default=str, json.dumps raises TypeError *inside* the handler;
        Python's logging then drops the record via handleError(). The formatter
        must degrade such values to their string form instead.
        """
        from datetime import datetime, timezone
        record = self._make_record("with extra")
        # datetime is the classic non-serializable type; also throw in a set.
        record.extra_data = {
            "when": datetime(2024, 6, 1, tzinfo=timezone.utc),
            "tags": {"a", "b"},
        }
        # Must not raise, and must still be valid JSON.
        output = self.formatter.format(record)
        data = json.loads(output)
        self.assertIn("extra", data)
        # datetime degraded to its str() form
        self.assertIn("2024-06-01", data["extra"]["when"])

    def test_custom_object_extra_is_stringified(self):
        class Widget:
            def __str__(self):
                return "WIDGET-42"
        record = self._make_record("obj extra")
        record.extra_data = {"widget": Widget()}
        data = json.loads(self.formatter.format(record))
        self.assertEqual(data["extra"]["widget"], "WIDGET-42")


class TestLoggingManager(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.lm = LoggingManager({"log_dir": self.tmpdir, "enable_console": False})

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        # Restore root logger handlers
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)
            h.close()

    def test_log_file_created(self):
        import os
        log_file = os.path.join(self.tmpdir, "otedama.log")
        self.assertTrue(os.path.exists(log_file))

    def test_set_log_level_valid(self):
        result = self.lm.set_log_level("DEBUG")
        self.assertTrue(result)

    def test_set_log_level_invalid_returns_false(self):
        result = self.lm.set_log_level("NONSENSE")
        self.assertFalse(result)

    def test_get_log_stats_returns_dict(self):
        stats = self.lm.get_log_stats()
        self.assertIsInstance(stats, dict)

    def test_get_log_stats_has_keys(self):
        stats = self.lm.get_log_stats()
        self.assertIn("line_count", stats)
        self.assertIn("file_size", stats)


class TestEncryptedFileHandlerRotation(unittest.TestCase):
    """EncryptedFileHandler.emit() must trigger rotation when maxBytes is set.

    Bug: the encrypted path wrote directly to self.stream without calling
    shouldRollover() / doRollover(), so log files grew without bound when
    encryption was active.
    Fix: call shouldRollover() before writing the encrypted payload.
    """

    def _make_handler(self, path, max_bytes):
        from logging_manager import CRYPTOGRAPHY_AVAILABLE, EncryptedFileHandler
        if not CRYPTOGRAPHY_AVAILABLE:
            self.skipTest("cryptography not available")
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        return EncryptedFileHandler(path, encryption_key=key, maxBytes=max_bytes, backupCount=1)

    def test_rotation_occurs_with_encryption(self):
        """After exceeding maxBytes the handler must create a backup file."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            log_path = os.path.join(d, "enc.log")
            handler = self._make_handler(log_path, max_bytes=500)
            logger_ = logging.getLogger("enc_test")
            logger_.addHandler(handler)
            try:
                for i in range(20):
                    logger_.warning("rotation test message %d — padding to trigger rollover", i)
            finally:
                logger_.removeHandler(handler)
                handler.close()
            # A backup file enc.log.1 should have been created
            backup_path = log_path + ".1"
            self.assertTrue(
                os.path.exists(backup_path),
                "Rotation backup enc.log.1 must exist after maxBytes exceeded with encryption"
            )
