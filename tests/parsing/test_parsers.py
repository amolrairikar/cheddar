"""Error handling; supported email shapes are covered by the files in cases/."""

import pytest
from conftest import cells
from email_parser.parsing import ParseError, parse_email


# Chase
def test_chase_unrelated_email_rejected(make_email):
    with pytest.raises(ParseError, match="no chase parser"):
        parse_email(make_email("chase", "Your statement is ready"))


def test_chase_zero_amount(make_email):
    with pytest.raises(ParseError, match="zero"):
        parse_email(make_email("chase", "You sent $0.00 from account ending in 1234"))


# Fidelity
FIDELITY = ["Account: X1234", "Symbol", "Acct Type", "Quantity", "Price", "Value",
            "VTI", "1", "10", "$200.00", "$2,000.00", "FXAIX", "1", "5.5", "$100.00", "$550.00", "Total $2,550.00"]


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
