import pytest
from email_parser.parsing import (
    Email,
    EmailParser,
    ParseError,
    ParserRegistry,
    Transaction,
    parse_email,
)


def test_unsupported_sender(make_email):
    with pytest.raises(ParseError, match="unsupported sender"):
        parse_email(make_email("someone@example.com"))


def test_malformed_dict():
    with pytest.raises(ParseError):
        parse_email({"message_id": "x"})


def test_new_institution_needs_no_core_changes(make_email):
    registry = ParserRegistry()

    @registry.register
    class FakeBank(EmailParser):
        institution = "fakebank"
        sender_hints = ("fakebank",)

        def parse(self, email: Email):
            return Transaction("shop", 1, "Fake 0000", email.date) if "shop" in email.subject else None

    assert registry.parse(make_email("alerts@fakebank.com", "shop")).account == "Fake 0000"
    with pytest.raises(ParseError, match="no fakebank parser"):
        registry.parse(make_email("alerts@fakebank.com", "other"))


def test_from_dict_valid(make_email):
    e = make_email("a@b.com", "s", "p", "h")
    data = {k: getattr(e, k) for k in ("message_id", "sender", "subject", "date", "plain", "html")}
    assert Email.from_dict(data) == e


def test_parsers_property_is_a_snapshot():
    registry = ParserRegistry()

    @registry.register
    class Bank(EmailParser):
        institution = "bank"
        sender_hints = ("bank",)

        def parse(self, email: Email):
            return None

    assert [p.institution for p in registry.parsers] == ["bank"]
