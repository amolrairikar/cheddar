"""Base class every institution parser implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from .models import Email, ParseResult


class EmailParser(ABC):
    """Parses one institution's emails.

    Set ``institution`` and ``sender_hints`` (lowercase substrings of the From
    header), then implement ``parse``. Return ``None`` when the email is not a
    shape this parser handles; raise ``ParseError`` when it is but is malformed.
    """

    institution: ClassVar[str]
    sender_hints: ClassVar[tuple[str, ...]]

    def matches_sender(self, email: Email) -> bool:
        sender = email.sender.lower()
        return any(hint in sender for hint in self.sender_hints)

    @abstractmethod
    def parse(self, email: Email) -> ParseResult | None: ...
