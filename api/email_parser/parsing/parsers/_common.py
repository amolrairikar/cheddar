"""Helpers shared by institution parsers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from ..models import ParseError

AMOUNT = r"([\d,]+\.\d{2})"


def parse_amount(raw: str) -> Decimal:
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation:
        raise ParseError(f"malformed amount {raw!r}") from None


def nonzero(value: Decimal) -> Decimal:
    if value == 0:
        raise ParseError("amount is zero")
    return value


def normalize_ws(text: str) -> str:
    return " ".join(text.split())
