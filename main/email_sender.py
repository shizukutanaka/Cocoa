"""
Email delivery abstraction for Cocoa.

Password reset and email verification generate single-use tokens that must be
delivered out-of-band (OWASP forgot-password guidance): returning them in the
API response either locks users out (reset: nothing was ever delivered) or
defeats the check entirely (verification: the caller can "verify" a mailbox
they don't own). This module provides that side channel.

Backends:
- ConsoleEmailSender (default): logs the full message. Local dev and E2E tests
  read delivery off the server log; nothing leaves the machine.
- SMTPEmailSender: stdlib smtplib, selected when COCOA_SMTP_HOST is set.

Config (house convention -- os.getenv with COCOA_* names):
  COCOA_SMTP_HOST      SMTP server; presence selects the SMTP backend
  COCOA_SMTP_PORT      default 587
  COCOA_SMTP_USER      optional; login performed only when set
  COCOA_SMTP_PASSWORD  optional
  COCOA_SMTP_FROM      From address (default no-reply@localhost)
  COCOA_SMTP_STARTTLS  default "true"

Choosing an actual mail provider (SendGrid etc.) is a business decision and is
out of scope here -- any provider that speaks SMTP works with this as-is.
"""
from __future__ import annotations

import logging
import os
import smtplib
import threading
from dataclasses import dataclass
from email.message import EmailMessage as _StdEmailMessage
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    to: str
    subject: str
    body_text: str


class ConsoleEmailSender:
    """Log the message instead of sending it. Development default.

    The log line is the delivery: E2E tests assert on it, and a local dev
    copies the link straight out of the console.
    """

    def send(self, msg: EmailMessage) -> bool:
        logger.info(
            "[ConsoleEmailSender] To: %s | Subject: %s\n%s",
            msg.to, msg.subject, msg.body_text,
        )
        return True


class SMTPEmailSender:
    """Deliver via a real SMTP server using only the stdlib."""

    def __init__(
        self,
        host: str,
        port: int = 587,
        username: str = "",
        password: str = "",
        from_addr: str = "no-reply@localhost",
        use_starttls: bool = True,
        timeout: float = 10.0,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.use_starttls = use_starttls
        self.timeout = timeout

    def send(self, msg: EmailMessage) -> bool:
        mime = _StdEmailMessage()
        mime["From"] = self.from_addr
        mime["To"] = msg.to
        mime["Subject"] = msg.subject
        mime.set_content(msg.body_text)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
                if self.use_starttls:
                    smtp.starttls()
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(mime)
            return True
        except Exception as exc:
            # The caller treats delivery as best-effort; never raise into a
            # request path. A reset request must return its uniform response
            # whether or not the mail relay is up.
            logger.error("SMTP send to %s failed: %s", msg.to, exc)
            return False


_sender = None
_sender_lock = threading.Lock()


def get_email_sender():
    """Return the process-wide sender: SMTP when COCOA_SMTP_HOST is set,
    otherwise the console logger."""
    global _sender
    if _sender is None:
        with _sender_lock:
            if _sender is None:
                host = os.getenv("COCOA_SMTP_HOST", "").strip()
                if host:
                    _sender = SMTPEmailSender(
                        host=host,
                        port=int(os.getenv("COCOA_SMTP_PORT", "587")),
                        username=os.getenv("COCOA_SMTP_USER", ""),
                        password=os.getenv("COCOA_SMTP_PASSWORD", ""),
                        from_addr=os.getenv("COCOA_SMTP_FROM", "no-reply@localhost"),
                        use_starttls=os.getenv("COCOA_SMTP_STARTTLS", "true").lower() == "true",
                    )
                    logger.info("Email delivery: SMTP via %s", host)
                else:
                    _sender = ConsoleEmailSender()
                    logger.info(
                        "Email delivery: console logger (set COCOA_SMTP_HOST "
                        "to deliver real mail)"
                    )
    return _sender


def send_email(to: str, subject: str, body_text: str) -> bool:
    """Best-effort convenience wrapper; returns False instead of raising."""
    try:
        return get_email_sender().send(EmailMessage(to=to, subject=subject, body_text=body_text))
    except Exception as exc:
        logger.error("Email send to %s failed: %s", to, exc)
        return False
