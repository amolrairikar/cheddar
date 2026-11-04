import pytest
from email_parser.loading import ImapConfig
from email_parser.loading import imap as imap_mod
from email_parser.parsing import Email
from imap_fakes import FakeIMAP

DATE = "2026-10-15T14:30:00+00:00"


@pytest.fixture
def make_email():
    def make(sender, subject="", plain="", html="", date=DATE):
        return Email("abc", sender, subject, date, plain, html)
    return make


@pytest.fixture
def fake_imap(monkeypatch):
    FakeIMAP.instances, FakeIMAP.messages = [], {}
    FakeIMAP.login_error, FakeIMAP.select_status = False, "OK"
    FakeIMAP.store_status, FakeIMAP.copy_error = "OK", False
    FakeIMAP.folders = {"transactions-processed": {}, "transactions-failed": {}}
    monkeypatch.setattr(imap_mod.imaplib, "IMAP4_SSL", FakeIMAP)
    return FakeIMAP


@pytest.fixture
def config():
    return ImapConfig("me@example.com", "s3cret-pw")


def cells(*lines):
    """HTML that renders one table cell per line."""
    return "<html><body><table>" + "".join(f"<tr><td>{l}</td></tr>" for l in lines) + "</table></body></html>"
