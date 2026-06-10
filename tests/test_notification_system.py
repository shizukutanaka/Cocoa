"""Tests for NotificationSystem — register handlers, send, clear."""
import logging
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))
from notification_system import NotificationSystem, ConsoleNotificationHandler, FileNotificationHandler


class TestNotificationSystem(unittest.TestCase):

    def setUp(self):
        self.logger = logging.getLogger("test_ns")
        self.ns = NotificationSystem(self.logger)

    def test_send_notification_stores_entry(self):
        self.ns.send_notification("T", "M")
        notes = self.ns.get_notifications()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["title"], "T")
        self.assertEqual(notes[0]["message"], "M")

    def test_send_notification_default_level_info(self):
        self.ns.send_notification("T", "M")
        self.assertEqual(self.ns.get_notifications()[0]["level"], "info")

    def test_send_notification_custom_level(self):
        self.ns.send_notification("T", "M", level="error")
        self.assertEqual(self.ns.get_notifications()[0]["level"], "error")

    def test_get_notifications_returns_list(self):
        self.assertIsInstance(self.ns.get_notifications(), list)

    def test_clear_notifications(self):
        self.ns.send_notification("T", "M")
        self.ns.clear_notifications()
        self.assertEqual(len(self.ns.get_notifications()), 0)

    def test_multiple_notifications_ordered(self):
        self.ns.send_notification("A", "first")
        self.ns.send_notification("B", "second")
        notes = self.ns.get_notifications()
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0]["title"], "A")
        self.assertEqual(notes[1]["title"], "B")


class TestConsoleNotificationHandler(unittest.TestCase):

    def test_send_does_not_raise(self):
        logger = logging.getLogger("test_cnh")
        handler = ConsoleNotificationHandler(logger)
        handler.send_notification({"title": "T", "message": "M", "level": "info"})


class TestFileNotificationHandler(unittest.TestCase):

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".log", delete=False)  # noqa: SIM115
        self.tmpfile.close()
        self.logger = logging.getLogger("test_fnh")
        self.handler = FileNotificationHandler(self.logger, self.tmpfile.name)

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_send_writes_to_file(self):
        self.handler.send_notification({"title": "T", "message": "M", "level": "info"})
        with open(self.tmpfile.name, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("T", content)

    def test_send_multiple_entries(self):
        self.handler.send_notification({"title": "A", "message": "first", "level": "info"})
        self.handler.send_notification({"title": "B", "message": "second", "level": "warning"})
        with open(self.tmpfile.name, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("A", content)
        self.assertIn("B", content)
