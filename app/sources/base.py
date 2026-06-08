"""Abstract email source interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Email


class EmailSource(ABC):
    """Anything that can hand the agent a batch of emails to process."""

    @abstractmethod
    def fetch(self) -> list[Email]:
        """Return the current batch of emails from the inbox."""
        raise NotImplementedError

    @property
    def name(self) -> str:
        return self.__class__.__name__
