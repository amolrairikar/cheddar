"""Capital One purchase alerts; the plain text carries every field in fixed sentences."""

from __future__ import annotations

import re

from ..base import EmailParser
from ..models import Email, Transaction
from ..registry import register
from ._common import AMOUNT, nonzero, normalize_ws, parse_amount

ACCOUNT = re.compile(r"About your\s+(.+?)\s+Card\s+ending\s+in\s+(\d{4})\b", re.IGNORECASE)
PURCHASE = re.compile(
    rf"\bat\s+(.+?),\s+a\s+(?:pending\s+authorization\s+or\s+)?purchase\s+in\s+the\s+amount\s+of\s+\${AMOUNT}\b",
    re.IGNORECASE | re.DOTALL,
)


@register
class CapitalOneParser(EmailParser):
    institution = "capital_one"
    sender_hints = ("capitalone",)

    def parse(self, email: Email) -> Transaction | None:
        account, sale = ACCOUNT.search(email.plain), PURCHASE.search(email.plain)
        if account is None or sale is None:
            return None
        return Transaction(normalize_ws(sale[1]), -nonzero(parse_amount(sale[2])),
                           f"{normalize_ws(account[1])} {account[2]}", email.date)
