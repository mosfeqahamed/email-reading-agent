"""Gmail email source — reads unseen messages from Gmail over IMAP.

Gmail is reached at imap.gmail.com:993 using an App Password (not your login
password). Only reads mail; never sends — there is no SMTP anywhere.
"""
from __future__ import annotations

import email
import imaplib
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from ..models import Email
from .base import EmailSource

GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _extract_body(msg: email.message.Message) -> str:
    """Pull the plain-text body out of a (possibly multipart) message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(
                part.get("Content-Disposition", "")
            ):
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    if payload:
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return ""


class GmailSource(EmailSource):
    def __init__(
        self,
        user: str,
        app_password: str,
        folder: str = "INBOX",
        max_fetch: int = 20,
    ) -> None:
        self.user = user
        self.app_password = app_password
        self.folder = folder
        # Safety cap: only process the most recent N unread emails per cycle, so
        # a huge backlog doesn't trigger thousands of classifications at once.
        self.max_fetch = max_fetch

    def fetch(self) -> list[Email]:
        emails: list[Email] = []
        conn = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST, GMAIL_IMAP_PORT)
        try:
            conn.login(self.user, self.app_password)
            # readonly=True means reading NEVER marks your real emails as read.
            conn.select(self.folder, readonly=True)
            status, data = conn.search(None, "UNSEEN")
            if status != "OK" or not data or not data[0]:
                return []

            # Take only the most recent N unread messages (highest ids = newest).
            ids = data[0].split()
            ids = ids[-self.max_fetch:]

            for num in ids:
                # BODY.PEEK[] fetches the full message WITHOUT setting the \Seen
                # flag, so the agent is completely non-destructive to your inbox.
                status, msg_data = conn.fetch(num, "(BODY.PEEK[])")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])

                # Message-ID is the stable, provider-assigned unique id.
                msg_id = _decode(msg.get("Message-ID")) or num.decode()
                received = ""
                if msg.get("Date"):
                    try:
                        received = parsedate_to_datetime(msg["Date"]).isoformat()
                    except Exception:
                        received = _decode(msg.get("Date"))

                emails.append(
                    Email(
                        id=msg_id,
                        sender=_decode(msg.get("From")),
                        subject=_decode(msg.get("Subject")),
                        body=_extract_body(msg),
                        received_at=received,
                    )
                )
        finally:
            try:
                conn.logout()
            except Exception:
                pass
        return emails
