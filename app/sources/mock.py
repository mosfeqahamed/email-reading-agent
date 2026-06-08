"""Mock email source — reads a local JSON file. No credentials required.

Mock mode is mandatory per the task so the project is fully testable offline.
"""
from __future__ import annotations

import json

from ..models import Email
from .base import EmailSource


class MockSource(EmailSource):
    def __init__(self, path: str = "data/mock_emails.json") -> None:
        self.path = path

    def fetch(self) -> list[Email]:
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [Email.from_mock(item) for item in raw]
