"""Fidelity position summaries: an account line, a positions table, and a Total line."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from ..base import EmailParser
from ..models import Email, InvestmentPosition, ParseError, PositionSummary
from ..registry import register
from ..text import email_text

ACCOUNT = re.compile(r"Account:?\s*X*(\d{4})\b", re.IGNORECASE)
HEADER = re.compile(r"Symbol\s+Acct\s+Type\s+Quantity\s+Price\s+Value", re.IGNORECASE)
TOTAL = re.compile(r"\bTotal\s+(-?\$?-?[\d,]+\.\d{2})\b", re.IGNORECASE)
TOLERANCE = Decimal("0.01")
COLUMNS = 5


def _number(token: str) -> Decimal:
    try:
        return Decimal(token.replace("$", "").replace(",", ""))
    except InvalidOperation:
        raise ParseError(f"malformed position value {token!r}") from None


@register
class FidelityParser(EmailParser):
    institution = "fidelity"
    sender_hints = ("fidelity",)

    def parse(self, email: Email) -> PositionSummary | None:
        text = email_text(email)
        account, header = ACCOUNT.search(text), HEADER.search(text)
        total = TOTAL.search(text, header.end()) if header else None
        if account is None or header is None or total is None:
            return None

        # Rows are five fields each, whether the table is one line per row or per cell.
        tokens = text[header.end():total.start()].split()
        if not tokens or len(tokens) % COLUMNS:
            raise ParseError("position table is malformed")
        label = f"Fidelity {account[1]}"
        positions = []
        for symbol, account_type, quantity, price, value in zip(*[iter(tokens)] * COLUMNS):
            if not account_type.isdigit():
                raise ParseError(f"unexpected account type {account_type!r}")
            positions.append(InvestmentPosition(
                ticker=symbol, quantity=_number(quantity), price=_number(price),
                value=_number(value), account=label, account_type=account_type,
                snapshot_date=email.date))
        balance = _number(total[1])
        if abs(sum(p.value for p in positions) - balance) > TOLERANCE:
            raise ParseError("positions do not add up to the Total")
        return PositionSummary(label, email.date, balance, tuple(positions))
