from __future__ import annotations

from . import parsers  # noqa: F401  (registers built-in parsers)
from .base import EmailParser
from .models import (
    Email,
    InvestmentPosition,
    ParseError,
    ParseResult,
    PositionSummary,
    Transaction,
)
from .registry import ParserRegistry, default_registry, register


def parse_email(email: Email | dict) -> ParseResult:
    if isinstance(email, dict):
        email = Email.from_dict(email)
    return default_registry.parse(email)


__all__ = ["Email", "EmailParser", "InvestmentPosition", "ParseError",
           "ParseResult", "ParserRegistry", "PositionSummary", "Transaction",
           "default_registry", "parse_email", "register"]
