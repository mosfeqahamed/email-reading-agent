"""The agent loop: fetch → dedup → classify → store, on a fixed interval.

Run with:  python -m app.agent
"""
from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv

from . import db
from .classifier import classify
from .sources import get_source

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("agent")


def process_once() -> dict:
    """Run a single poll cycle. Returns a small summary for logging/tests."""
    source = get_source()
    emails = source.fetch()
    log.info("Fetched %d email(s) from %s", len(emails), source.name)

    new = important = 0
    for email in emails:
        # Duplicate prevention: skip anything we've already handled.
        if db.is_processed(email.id):
            continue
        new += 1

        decision = classify(email)
        db.mark_processed(email.id)

        if decision.important:
            db.add_notification(email, decision)
            important += 1
            log.info(
                "IMPORTANT [%s/%s] %s — %s",
                decision.priority,
                decision.category,
                email.subject[:60],
                decision.reason[:80],
            )
        else:
            log.info("ignored: %s", email.subject[:60])

    log.info("Cycle done: %d new, %d important", new, important)
    return {"fetched": len(emails), "new": new, "important": important}


def run_forever() -> None:
    db.init_db()
    interval = int(os.getenv("POLL_INTERVAL", "120"))
    source_kind = os.getenv("EMAIL_SOURCE", "mock")
    log.info(
        "Agent starting. source=%s interval=%ss deepseek=%s",
        source_kind,
        interval,
        "on" if os.getenv("DEEPSEEK_API_KEY") else "off (rules only)",
    )
    while True:
        try:
            process_once()
        except Exception:
            log.exception("Poll cycle failed; will retry next interval")
        time.sleep(interval)


if __name__ == "__main__":
    run_forever()
