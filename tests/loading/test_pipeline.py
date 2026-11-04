import logging
from decimal import Decimal

from email_parser.loading import ImapLoader, LoadedEmail, load_and_parse, pipeline
from email_parser.parsing import Email
from email_parser.parsing.models import Transaction
from imap_fakes import build


class StubLoader:
    def __init__(self, items):
        self.items = items

    def fetch_raw(self):
        return self.items


def item(uid, sender):
    return LoadedEmail(uid, Email(uid, sender, "s", "2026-10-15T14:30:00+00:00", "", "")), uid


def test_mixed_batch(monkeypatch):
    tx = Transaction("m", Decimal(-1), "a", "t")

    def fake_parse(email):
        if email.sender == "good":
            return tx
        from email_parser.parsing import ParseError
        raise ParseError("bad " + email.sender)

    monkeypatch.setattr(pipeline, "parse_email", fake_parse)
    result = load_and_parse(StubLoader([item("1", "good"), item("2", "malformed"),
                                        item("3", "unknown"), (None, "4")]))
    assert [(p.uid, p.result) for p in result.parsed] == [("1", tx)]
    assert [f.uid for f in result.failed] == ["2", "3", "4"]


def test_parsed_entry_carries_message_id(monkeypatch):
    tx = Transaction("m", Decimal(-1), "a", "t")
    monkeypatch.setattr(pipeline, "parse_email", lambda email: tx)
    loaded = LoadedEmail("7", Email("<abc@x>", "good", "s", "2026-10-15T14:30:00+00:00", "", ""))
    result = load_and_parse(StubLoader([(loaded, "7")]))
    assert [(p.uid, p.message_id) for p in result.parsed] == [("7", "<abc@x>")]


def test_message_id_falls_back_to_uid(fake_imap, config, monkeypatch):
    tx = Transaction("m", Decimal(-1), "a", "t")
    monkeypatch.setattr(pipeline, "parse_email", lambda email: tx)
    fake_imap.messages = {"5": bytes(build(message_id=None))}
    with ImapLoader(config) as loader:
        result = load_and_parse(loader)
    assert [(p.uid, p.message_id) for p in result.parsed] == [("5", "5")]


def test_unrecognized_sender_with_real_parsers():
    result = load_and_parse(StubLoader([item("9", "nobody@nowhere.example")]))
    assert result.parsed == [] and result.failed[0].uid == "9"


def test_empty_folder():
    result = load_and_parse(StubLoader([]))
    assert result.parsed == [] and result.failed == []


def test_end_to_end_with_fake_imap(fake_imap, config):
    fake_imap.messages = {"1": bytes(build(sender="x@unknown.example"))}
    with ImapLoader(config) as loader:
        result = load_and_parse(loader)
    assert [f.uid for f in result.failed] == ["1"]


def test_debug_outcome_logged(caplog):
    with caplog.at_level(logging.DEBUG, logger="email_parser"):
        load_and_parse(StubLoader([item("5", "nobody@nowhere.example")]))
    assert "uid=5 failed" in caplog.text
