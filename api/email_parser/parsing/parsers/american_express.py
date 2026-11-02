"""American Express large purchase alerts (HTML only).

Converted to text, the body has one cell per line, e.g.::

    Account Ending: 12345
    UNITED ELEC TICKETNG
    $8.00*

The merchant is the line before the starred amount; the trailing ``*`` excludes
other amounts such as the alert threshold.
"""

from __future__ import annotations

import re

from ..base import EmailParser
from ..models import Email, Transaction
from ..registry import register
from ..text import email_text
from ._common import AMOUNT, nonzero, parse_amount

ACCOUNT = re.compile(r"Account Ending: (\d+)")
PURCHASE = re.compile(rf"^([^\r\n]+?)[ \t\r]*\n(?:[ \t\r]*\n)*\${AMOUNT}\*", re.MULTILINE)


@register
class AmericanExpressParser(EmailParser):
    institution = "american_express"
    sender_hints = ("americanexpress",)

    def parse(self, email: Email) -> Transaction | None:
        text = email_text(email)
        account, sale = ACCOUNT.search(text), PURCHASE.search(text)
        if account is None or sale is None:
            return None
        return Transaction(sale[1].strip(), -nonzero(parse_amount(sale[2])),
                           f"American Express {account[1]}", email.date)
