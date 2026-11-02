"""Chase: direct deposits and transfers (subject), card transaction alerts (body)."""

from __future__ import annotations

import re

from ..base import EmailParser
from ..models import Email, Transaction
from ..registry import register
from ..text import email_text
from ._common import AMOUNT, nonzero, normalize_ws, parse_amount

_ENDING = r"account ending in \(?\.*(\d{4})\)?"
DIRECT_DEPOSIT = re.compile(rf"\${AMOUNT} direct deposit posted to {_ENDING}", re.IGNORECASE)
TRANSFER = re.compile(rf"\bYou sent \${AMOUNT} from {_ENDING}", re.IGNORECASE)
# Body fields: "Account United Quest Visa (...1234)", "Merchant UBER *TRIP", "Amount $17.99".
ACCOUNT = re.compile(r"^Account\s+(.+?)\s*\(\.\.\.(\d{4})\)", re.MULTILINE)
MERCHANT = re.compile(r"^Merchant\s+([^\r\n]+)", re.MULTILINE)
CARD_AMOUNT = re.compile(rf"^Amount\s+\${AMOUNT}", re.MULTILINE)


@register
class ChaseParser(EmailParser):
    institution = "chase"
    sender_hints = ("chase",)

    def parse(self, email: Email) -> Transaction | None:
        return (
            self._direct_deposit(email)
            or self._transfer(email)
            or self._card_transaction(email)
        )

    def _direct_deposit(self, email: Email) -> Transaction | None:
        m = DIRECT_DEPOSIT.search(email.subject)
        if m is None:
            return None
        return Transaction("direct deposit", nonzero(parse_amount(m[1])),
                           f"Chase Checking {m[2]}", email.date)

    def _transfer(self, email: Email) -> Transaction | None:
        m = TRANSFER.search(email.subject)
        if m is None:
            return None
        # The subject names no recipient, so the merchant is left blank.
        return Transaction("", -nonzero(parse_amount(m[1])),
                           f"Chase Checking {m[2]}", email.date)

    def _card_transaction(self, email: Email) -> Transaction | None:
        text = email_text(email)
        account, merchant, amount = (
            ACCOUNT.search(text), MERCHANT.search(text), CARD_AMOUNT.search(text))
        if account is None or merchant is None or amount is None:
            return None
        return Transaction(normalize_ws(merchant[1]), -nonzero(parse_amount(amount[1])),
                           f"{normalize_ws(account[1])} {account[2]}", email.date)
