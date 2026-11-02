import logging

import pytest
from email_parser.loading import ImapLoader, LoaderError, message_to_email
from imap_fakes import build


def test_multipart_and_utc_date_and_sender():
    e = message_to_email(build(sender='"Capital One | Venture X" <c@n.example.com>'), "7")
    assert e.plain.strip() == "plain body"
    assert "html body" in e.html
    assert e.date == "2026-10-29T22:01:51+00:00"
    assert e.sender == "Capital One | Venture X <c@n.example.com>"
    assert e.message_id == "<m1@x>"


def test_missing_bodies_empty_and_uid_fallback():
    e = message_to_email(build(html="", message_id=None), "42")
    assert e.html == ""
    assert e.message_id == "42"


def test_fetch_is_read_only(fake_imap, config):
    fake_imap.messages = {"1": bytes(build())}
    with ImapLoader(config) as loader:
        emails = loader.fetch_emails()
    assert [m.uid for m in emails] == ["1"]
    calls = fake_imap.instances[0].calls
    assert ("select", '"transactions-pending"', True) in calls
    assert ("uid", "FETCH", "1", "(BODY.PEEK[])") in calls
    assert calls[-1] == ("logout",)


def test_login_failure_hides_password(fake_imap, config):
    fake_imap.login_error = True
    with pytest.raises(LoaderError) as exc:
        ImapLoader(config).__enter__()
    assert "s3cret-pw" not in str(exc.value)


def test_missing_folder(fake_imap, config):
    fake_imap.select_status = "NO"
    with ImapLoader(config) as loader, pytest.raises(LoaderError, match="transactions-pending"):
        loader.fetch_emails()


def test_debug_logs_contents_not_password(fake_imap, config, caplog):
    fake_imap.messages = {"1": bytes(build(subject="Subj"))}
    with caplog.at_level(logging.DEBUG, logger="email_parser"), ImapLoader(config) as loader:
        loader.fetch_emails()
    text = caplog.text
    assert "Subj" in text and "plain body" in text and "html body" in text
    assert "s3cret-pw" not in text


def test_failed_login_does_not_log_password(fake_imap, config, caplog):
    fake_imap.login_error = True
    with caplog.at_level(logging.DEBUG, logger="email_parser"), pytest.raises(LoaderError):
        ImapLoader(config).__enter__()
    assert "s3cret-pw" not in caplog.text


def test_info_omits_bodies(fake_imap, config, caplog):
    fake_imap.messages = {"1": bytes(build())}
    with caplog.at_level(logging.INFO, logger="email_parser"), ImapLoader(config) as loader:
        loader.fetch_emails()
    assert "plain body" not in caplog.text
    assert "1 message" in caplog.text


def _raw(headers: str, body: str = "body") -> bytes:
    return f"{headers}\r\n\r\n{body}".encode()


def test_body_falls_back_when_charset_unknown():
    from email import message_from_bytes, policy

    raw = _raw("From: a@b.com\r\nDate: Thu, 29 Oct 2026 18:01:51 -0400\r\n"
               "Content-Type: text/plain; charset=bogus-charset")
    e = message_to_email(message_from_bytes(raw, policy=policy.default), "1")
    assert e.plain.strip() == "body"


def test_missing_date_rejected():
    msg = build()
    del msg["Date"]
    with pytest.raises(ValueError, match="Date"):
        message_to_email(msg, "1")


def test_naive_date_treated_as_utc():
    e = message_to_email(build(date="Thu, 29 Oct 2026 18:01:51 -0000"), "1")
    assert e.date == "2026-10-29T18:01:51+00:00"


def test_connection_error_is_loader_error(fake_imap, config, monkeypatch):
    def boom(host, port):
        raise OSError("network down")

    monkeypatch.setattr("email_parser.loading.imap.imaplib.IMAP4_SSL", boom)
    with pytest.raises(LoaderError, match="could not log in"):
        ImapLoader(config).__enter__()


def test_logout_errors_are_ignored(fake_imap, config, monkeypatch):
    def bad_logout(self):
        raise OSError("already closed")

    monkeypatch.setattr(fake_imap, "logout", bad_logout)
    with ImapLoader(config):
        pass


def test_fetch_requires_context_manager(config):
    with pytest.raises(LoaderError, match="not connected"):
        ImapLoader(config).fetch_raw()


def test_select_error_is_loader_error(fake_imap, config, monkeypatch):
    import imaplib

    def bad_select(self, folder, readonly=False):
        raise imaplib.IMAP4.error("boom")

    monkeypatch.setattr(fake_imap, "select", bad_select)
    with ImapLoader(config) as loader, pytest.raises(LoaderError, match="could not select"):
        loader.fetch_raw()


def test_search_failure(fake_imap, config, monkeypatch):
    monkeypatch.setattr(fake_imap, "uid", lambda self, *a: ("NO", [b""]))
    with ImapLoader(config) as loader, pytest.raises(LoaderError, match="search failed"):
        loader.fetch_raw()


def test_empty_folder(fake_imap, config):
    with ImapLoader(config) as loader:
        assert loader.fetch_raw() == []


def test_unfetchable_and_unconvertible_messages_reported(fake_imap, config, monkeypatch):
    no_date = _raw("From: a@b.com")
    fake_imap.messages = {"1": bytes(build()), "2": b"", "3": no_date, "4": b""}

    def uid(self, command, *args):
        if command == "SEARCH":
            return "OK", [b"1 2 3 4"]
        if args[0] == "2":
            return "NO", [None]
        if args[0] == "4":
            return "OK", [b")"]  # no message tuple
        return "OK", [(b"x", fake_imap.messages[args[0]]), b")"]

    monkeypatch.setattr(fake_imap, "uid", uid)
    with ImapLoader(config) as loader:
        results = loader.fetch_raw()
    assert [(r is not None, u) for r, u in results] == [(True, "1"), (False, "2"), (False, "3"), (False, "4")]
