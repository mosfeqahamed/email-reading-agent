"""Core data structures shared across the agent and dashboard."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal

Priority = Literal["HIGH", "MEDIUM", "LOW"]


@dataclass
class Email:
    """A single email pulled from a source (mock, IMAP, or Gmail)."""
    id: str
    sender: str
    subject: str
    body: str
    received_at: str  # ISO-8601 timestamp

    @classmethod
    def from_mock(cls, raw: dict) -> "Email":
        return cls(
            id=str(raw["id"]),
            sender=raw.get("from", "unknown"),
            subject=raw.get("subject", ""),
            body=raw.get("body", ""),
            received_at=raw.get("received_at", ""),
        )


@dataclass
class Decision:
    """The structured classification result for one email."""
    important: bool
    priority: Priority
    category: str
    reason: str
    source: str  # "rules" or "deepseek" — how the decision was reached

    def to_dict(self) -> dict:
        return asdict(self)
