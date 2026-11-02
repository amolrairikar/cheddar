"""Data model shared by all email parsers."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


class ParseError(ValueError):
    """The email is unsupported, or belongs to a parser but is malformed."""


@dataclass(frozen=True)
class Email:
    message_id: str
    sender: str
    subject: str
    date: str  # Date header as UTC ISO 8601
    plain: str = ""
    html: str = ""

    _REQUIRED = ("message_id", "sender", "subject", "date", "plain", "html")

    @classmethod
    def from_dict(cls, data: dict) -> Email:
        for name in cls._REQUIRED:
            if not isinstance(data.get(name), str):
                raise ParseError(f"email field {name!r} must be a string")
        return cls(**{name: data[name] for name in cls._REQUIRED})


@dataclass(frozen=True)
class Transaction:
    merchant: str
    amount: Decimal  # negative = spent, positive = received
    account: str
    timestamp: str


@dataclass(frozen=True)
class InvestmentPosition:
    ticker: str
    quantity: Decimal
    price: Decimal
    value: Decimal
    account: str
    account_type: str
    snapshot_date: str


@dataclass(frozen=True)
class PositionSummary:
    account: str
    snapshot_date: str
    balance: Decimal
    positions: tuple[InvestmentPosition, ...]


ParseResult = Transaction | PositionSummary
