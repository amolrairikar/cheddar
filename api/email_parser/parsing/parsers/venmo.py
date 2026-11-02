"""Venmo payment emails; the subject carries every field."""

from __future__ import annotations

import re

from ..base import EmailParser
from ..models import Email, Transaction
from ..registry import register
from ._common import AMOUNT, nonzero, normalize_ws, parse_amount

PAID = re.compile(rf"^You paid\s+(.+?)\s+\${AMOUNT}\s*$", re.IGNORECASE)
RECEIVED = re.compile(rf"^(.+?)\s+paid\s+\${AMOUNT}\s+to your Venmo account\b", re.IGNORECASE)
REQUEST_PAID = re.compile(rf"^(.+?)\s+paid\s+your\s+\${AMOUNT}\s+request\b", re.IGNORECASE)


@register
class VenmoParser(EmailParser):
    institution = "venmo"
    sender_hints = ("venmo",)

    def parse(self, email: Email) -> Transaction | None:
        subject = email.subject.strip()
        if m := PAID.search(subject):
            sign = -1
        elif (m := RECEIVED.search(subject)) or (m := REQUEST_PAID.search(subject)):
            sign = 1
        else:
            return None
        return Transaction(normalize_ws(m[1]), sign * nonzero(parse_amount(m[2])),
                           "Venmo", email.date)
