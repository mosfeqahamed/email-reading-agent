"""SQLite persistence: duplicate prevention + the important-email feed.

A single SQLite file is shared (via a Docker volume) between the agent
process that writes notifications and the dashboard process that reads them.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager

from .models import Decision, Email

DB_PATH = os.getenv("DB_PATH", "data/agent.db")

# SQLite connections can't be shared across threads, so guard with a lock and
# open short-lived connections. WAL mode lets the reader (dashboard) and writer
# (agent) work concurrently without blocking each other.
_lock = threading.Lock()


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with _lock, _connect() as conn:
        # Every email we've ever seen — the duplicate-prevention ledger.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_emails (
                email_id     TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        # Only the important emails surface here as dashboard notifications.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                email_id     TEXT PRIMARY KEY,
                sender       TEXT NOT NULL,
                subject      TEXT NOT NULL,
                priority     TEXT NOT NULL,
                category     TEXT NOT NULL,
                reason       TEXT NOT NULL,
                received_at  TEXT NOT NULL,
                decided_by   TEXT NOT NULL,
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


def is_processed(email_id: str) -> bool:
    """Has this email already been handled? Core of duplicate prevention."""
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_emails WHERE email_id = ?", (email_id,)
        ).fetchone()
        return row is not None


def mark_processed(email_id: str) -> None:
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_emails (email_id) VALUES (?)",
            (email_id,),
        )


def add_notification(email: Email, decision: Decision) -> None:
    """Persist an important email so the dashboard can display it once."""
    with _lock, _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO notifications
                (email_id, sender, subject, priority, category, reason,
                 received_at, decided_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email.id,
                email.sender,
                email.subject,
                decision.priority,
                decision.category,
                decision.reason,
                email.received_at,
                decision.source,
            ),
        )


def get_notifications() -> list[dict]:
    """All important notifications, highest priority and newest first."""
    priority_rank = "CASE priority WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END"
    with _lock, _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM notifications ORDER BY {priority_rank}, created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def stats() -> dict:
    """Small summary used by the dashboard header."""
    with _lock, _connect() as conn:
        processed = conn.execute("SELECT COUNT(*) FROM processed_emails").fetchone()[0]
        important = conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
        return {"processed": processed, "important": important}
