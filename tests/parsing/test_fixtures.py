"""Parse redacted real emails from tests/fixtures through the loader's conversion."""

from decimal import Decimal
from email import message_from_binary_file, policy
from pathlib import Path

from email_parser.loading import message_to_email
from email_parser.parsing import (
    InvestmentPosition,
    PositionSummary,
    Transaction,
    parse_email,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load(institution, name):
    with open(FIXTURES / institution / name, "rb") as f:
        msg = message_from_binary_file(f, policy=policy.default)
    return message_to_email(msg, uid="fixture")


def test_capital_one_credit_card_transaction():
    email = load("capital_one", "credit_card_transaction.eml")
    assert email.sender == "Capital One | Venture X <capitalone@notification.capitalone.com>"
    assert email.date == "2026-10-29T22:01:51+00:00"
    assert parse_email(email) == Transaction(
        merchant="Whole Foods Market",
        amount=Decimal("-12.34"),
        account="Venture X 1234",
        timestamp="2026-10-29T22:01:51+00:00",
    )



def test_venmo_payment_sent():
    email = load("venmo", "payment_sent.eml")
    assert parse_email(email) == Transaction(
        "Jane Doe", Decimal("-5.00"), "Venmo", "2026-10-27T14:27:25+00:00")


def test_venmo_payment_received():
    email = load("venmo", "payment_received.eml")
    assert parse_email(email) == Transaction(
        "John Doe", Decimal("48.50"), "Venmo", "2026-11-01T20:54:25+00:00")



def test_chase_direct_deposit():
    email = load("chase", "direct_deposit.eml")
    assert parse_email(email) == Transaction(
        "direct deposit", Decimal("1000.00"), "Chase Checking 1234", "2026-10-30T08:00:55+00:00")


def test_chase_transfer():
    email = load("chase", "transfer.eml")
    assert parse_email(email) == Transaction(
        "", Decimal("-500.00"), "Chase Checking 1234", "2026-10-30T20:36:51+00:00")



def test_american_express_large_purchase():
    email = load("american_express", "credit_card_transaction.eml")
    assert parse_email(email) == Transaction(
        "UBER ONE", Decimal("-9.99"), "American Express 12345", "2026-10-26T13:56:05+00:00")



def test_chase_card_transaction():
    email = load("chase", "credit_card_transaction.eml")
    assert parse_email(email) == Transaction(
        "EXAMPLE *STORE ABC123", Decimal("-0.02"),
        "Chase Freedom Unlimited Visa 1234", "2026-11-01T18:22:55+00:00")


def test_fidelity_position_summary():
    email = load("fidelity", "investment_snapshot.eml")
    snapshot = "2026-10-30T10:52:16+00:00"

    def position(ticker, quantity, price, value):
        return InvestmentPosition(ticker, Decimal(quantity), Decimal(price), Decimal(value),
                                  "Fidelity 1234", "1", snapshot)

    assert parse_email(email) == PositionSummary(
        "Fidelity 1234", snapshot, Decimal("350.00"),
        (position("FDRXX", "100.00000", "1.00", "100.00"),
         position("FZROX", "10.00000", "25.00", "250.00")))
