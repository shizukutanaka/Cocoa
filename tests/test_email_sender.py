"""Tests for main/email_sender.py and the token-exposure contract.

The delivery abstraction exists because reset/verification tokens must travel
out-of-band: in-band reset tokens would let any caller reset any account, and
an in-band verification token proves nothing about mailbox ownership.
"""
import logging
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "main"))

# Other suites in this directory put main/ itself on sys.path, which makes
# `main` resolve to main/main.py (the tkinter launcher) instead of the package
# when suites run together -- so import the module flat, like they do.
import email_sender as es  # noqa: E402


class TestConsoleEmailSender(unittest.TestCase):
    def test_logs_full_message_and_reports_success(self):
        sender = es.ConsoleEmailSender()
        with self.assertLogs(es.logger, level=logging.INFO) as cm:
            ok = sender.send(es.EmailMessage("a@b.example", "Subj", "Body line"))
        self.assertTrue(ok)
        joined = "\n".join(cm.output)
        self.assertIn("a@b.example", joined)
        self.assertIn("Subj", joined)
        self.assertIn("Body line", joined)


class TestSMTPEmailSender(unittest.TestCase):
    def _sender(self, **kw):
        defaults = dict(host="smtp.example", port=2525, username="u", password="p",
                        from_addr="from@example", use_starttls=True)
        defaults.update(kw)
        return es.SMTPEmailSender(**defaults)

    def test_sends_via_smtp_with_starttls_and_login(self):
        with patch.object(es.smtplib, "SMTP") as smtp_cls:
            conn = smtp_cls.return_value.__enter__.return_value
            ok = self._sender().send(es.EmailMessage("to@example", "S", "B"))
        self.assertTrue(ok)
        smtp_cls.assert_called_once_with("smtp.example", 2525, timeout=10.0)
        conn.starttls.assert_called_once()
        conn.login.assert_called_once_with("u", "p")
        (mime,), _ = conn.send_message.call_args
        self.assertEqual(mime["To"], "to@example")
        self.assertEqual(mime["From"], "from@example")
        self.assertEqual(mime["Subject"], "S")

    def test_no_login_without_username(self):
        with patch.object(es.smtplib, "SMTP") as smtp_cls:
            conn = smtp_cls.return_value.__enter__.return_value
            self._sender(username="", password="").send(es.EmailMessage("t@e", "S", "B"))
        conn.login.assert_not_called()

    def test_starttls_can_be_disabled(self):
        with patch.object(es.smtplib, "SMTP") as smtp_cls:
            conn = smtp_cls.return_value.__enter__.return_value
            self._sender(use_starttls=False).send(es.EmailMessage("t@e", "S", "B"))
        conn.starttls.assert_not_called()

    def test_smtp_failure_returns_false_not_raise(self):
        """Delivery is best-effort: a dead relay must not break the request
        path that triggered the mail."""
        with patch.object(es.smtplib, "SMTP", side_effect=OSError("relay down")):
            ok = self._sender().send(es.EmailMessage("t@e", "S", "B"))
        self.assertFalse(ok)


class TestSenderSelection(unittest.TestCase):
    def setUp(self):
        es._sender = None  # reset the singleton between tests

    def tearDown(self):
        es._sender = None

    def test_console_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COCOA_SMTP_HOST", None)
            self.assertIsInstance(es.get_email_sender(), es.ConsoleEmailSender)

    def test_smtp_when_host_configured(self):
        with patch.dict(os.environ, {"COCOA_SMTP_HOST": "mail.example",
                                     "COCOA_SMTP_PORT": "465",
                                     "COCOA_SMTP_STARTTLS": "false"}):
            sender = es.get_email_sender()
        self.assertIsInstance(sender, es.SMTPEmailSender)
        self.assertEqual(sender.host, "mail.example")
        self.assertEqual(sender.port, 465)
        self.assertFalse(sender.use_starttls)

    def test_send_email_never_raises(self):
        broken = MagicMock()
        broken.send.side_effect = RuntimeError("boom")
        es._sender = broken
        self.assertFalse(es.send_email("t@e", "S", "B"))


if __name__ == "__main__":
    unittest.main()
