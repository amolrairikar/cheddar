from decimal import Decimal

import pytest
from conftest import DATE, cells
from email_parser.parsing import ParseError, PositionSummary, Transaction, parse_email


def tx(merchant, amount, account):
    return Transaction(merchant, Decimal(amount), account, DATE)


# Chase
def test_chase_direct_deposit(make_email):
    e = make_email("Chase <no-reply@chase.com>", "$1,234.56 direct deposit posted to account ending in (...1234)")
    assert parse_email(e) == tx("direct deposit", "1234.56", "Chase Checking 1234")


def test_chase_transfer(make_email):
    e = make_email("alerts@chase.com", "You sent $50.00 from account ending in 9876")
    assert parse_email(e) == tx("", "-50.00", "Chase Checking 9876")


def test_chase_card(make_email):
    html = cells("Account", "United Quest Visa (...1234)") .replace("</td></tr><tr><td>", " ")
    html = cells("Account United Quest Visa (...1234)", "Merchant UBER *TRIP", "Amount $17.99")
    assert parse_email(make_email("chase", html=html)) == tx("UBER *TRIP", "-17.99", "United Quest Visa 1234")


def test_chase_unrelated_email_rejected(make_email):
    with pytest.raises(ParseError, match="no chase parser"):
        parse_email(make_email("chase", "Your statement is ready"))


def test_chase_zero_amount(make_email):
    with pytest.raises(ParseError, match="zero"):
        parse_email(make_email("chase", "You sent $0.00 from account ending in 1234"))


# American Express
def test_amex(make_email):
    html = cells("Account Ending: 12345", "Threshold $1.00", "UNITED ELEC TICKETNG", "", "$8.00*")
    assert parse_email(make_email("AmericanExpress@welcome.americanexpress.com", html=html)) == tx(
        "UNITED ELEC TICKETNG", "-8.00", "American Express 12345")


# Capital One
def test_capital_one_wrapped(make_email):
    plain = "About your Venture X Card ending in 4950\nat  Corner\nCafe, a pending authorization or purchase in the amount of $1,200.50 was made."
    assert parse_email(make_email('"Capital One" <alerts@notification.capitalone.com>', plain=plain)) == tx(
        "Corner Cafe", "-1200.50", "Venture X 4950")


# Venmo
def test_venmo_paid_and_received(make_email):
    assert parse_email(make_email("venmo@venmo.com", "You paid Jane Doe $12.00")) == tx("Jane Doe", "-12.00", "Venmo")
    assert parse_email(make_email("venmo@venmo.com", "Jane Doe paid $5.25 to your Venmo account")) == tx(
        "Jane Doe", "5.25", "Venmo")


def test_venmo_request_paid(make_email):
    assert parse_email(make_email("venmo@venmo.com", "Jane Doe paid your $48.50 request")) == tx(
        "Jane Doe", "48.50", "Venmo")


# Fidelity
FIDELITY = ["Account: X1234", "Symbol", "Acct Type", "Quantity", "Price", "Value",
            "VTI", "1", "10", "$200.00", "$2,000.00", "FXAIX", "1", "5.5", "$100.00", "$550.00", "Total $2,550.00"]


def test_fidelity(make_email):
    result = parse_email(make_email("fidelity", html=cells(*FIDELITY)))
    assert isinstance(result, PositionSummary)
    assert result.account == "Fidelity 1234" and result.balance == Decimal("2550.00")
    assert [p.ticker for p in result.positions] == ["VTI", "FXAIX"]


def test_fidelity_total_mismatch(make_email):
    bad = FIDELITY[:-1] + ["Total $9.00"]
    with pytest.raises(ParseError, match="add up"):
        parse_email(make_email("fidelity", html=cells(*bad)))


def test_fidelity_unrelated_email_rejected(make_email):
    with pytest.raises(ParseError, match="no fidelity parser"):
        parse_email(make_email("fidelity", "Your statement is ready"))


def test_fidelity_malformed_table(make_email):
    bad = FIDELITY[:7] + FIDELITY[8:]  # drop one cell
    with pytest.raises(ParseError, match="malformed"):
        parse_email(make_email("fidelity", html=cells(*bad)))


def test_fidelity_empty_table(make_email):
    empty = ["Account: X1234", "Symbol", "Acct Type", "Quantity", "Price", "Value", "Total $0.00"]
    with pytest.raises(ParseError, match="malformed"):
        parse_email(make_email("fidelity", html=cells(*empty)))


def test_fidelity_non_numeric_account_type(make_email):
    bad = FIDELITY[:7] + ["Margin"] + FIDELITY[8:]
    with pytest.raises(ParseError, match="account type"):
        parse_email(make_email("fidelity", html=cells(*bad)))


def test_fidelity_malformed_number(make_email):
    bad = FIDELITY[:10] + ["abc"] + FIDELITY[11:]
    with pytest.raises(ParseError, match="malformed position value"):
        parse_email(make_email("fidelity", html=cells(*bad)))


# Unrecognized emails from known senders
def test_amex_unrelated_email_rejected(make_email):
    with pytest.raises(ParseError, match="no american_express parser"):
        parse_email(make_email("americanexpress", html=cells("Hello")))


def test_capital_one_unrelated_email_rejected(make_email):
    with pytest.raises(ParseError, match="no capital_one parser"):
        parse_email(make_email("capitalone", plain="Hello"))


def test_venmo_unrelated_email_rejected(make_email):
    with pytest.raises(ParseError, match="no venmo parser"):
        parse_email(make_email("venmo", "Welcome to Venmo"))


def test_parse_amount_malformed():
    from email_parser.parsing.parsers._common import parse_amount

    with pytest.raises(ParseError, match="malformed amount"):
        parse_amount("abc")
