"""Email source selection based on the EMAIL_SOURCE env var."""
from __future__ import annotations

import os

from .base import EmailSource
from .mock import MockSource
from .gmail import GmailSource


def get_source() -> EmailSource:
    """Return the configured email source. Defaults to mock (no creds needed)."""
    kind = os.getenv("EMAIL_SOURCE", "mock").strip().lower()

    if kind == "mock":
        return MockSource(path=os.getenv("MOCK_PATH", "data/mock_emails.json"))

    if kind == "gmail":
        return GmailSource(
            user=os.environ["GMAIL_USER"],
            app_password=os.environ["GMAIL_APP_PASSWORD"],
            folder=os.getenv("IMAP_FOLDER", "INBOX"),
            max_fetch=int(os.getenv("GMAIL_MAX_FETCH", "20")),
        )

    raise ValueError(f"Unknown EMAIL_SOURCE: {kind!r} (use mock | gmail)")
