"""Parser registry: selects parsers by sender and tries them in order."""

from __future__ import annotations

from .base import EmailParser
from .models import Email, ParseError, ParseResult


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: list[EmailParser] = []

    def register(self, parser_cls: type[EmailParser]) -> type[EmailParser]:
        """Register a parser class; usable as a decorator."""
        self._parsers.append(parser_cls())
        return parser_cls

    @property
    def parsers(self) -> tuple[EmailParser, ...]:
        return tuple(self._parsers)

    def parse(self, email: Email) -> ParseResult:
        candidates = [p for p in self._parsers if p.matches_sender(email)]
        if not candidates:
            raise ParseError(f"unsupported sender {email.sender!r}")
        for parser in candidates:
            result = parser.parse(email)
            if result is not None:
                return result
        names = ", ".join(p.institution for p in candidates)
        raise ParseError(f"no {names} parser matches this email")


default_registry = ParserRegistry()
register = default_registry.register
