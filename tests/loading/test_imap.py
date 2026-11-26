import imaplib
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
    def boom(host, port, timeout):
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
    assert [(r is not None, u, d) for r, u, d in results] == [
        (True, "1", True), (False, "2", False), (False, "3", True), (False, "4", False)]


def _pending(fake_imap, count=3):
    fake_imap.messages = {str(i): bytes(build()) for i in range(1, count + 1)}


def test_move_relocates_only_given_messages(fake_imap, config):
    _pending(fake_imap)
    with ImapLoader(config) as loader:
        loader.move(["1", "2"], "transactions-processed")
    assert set(fake_imap.folders["transactions-processed"]) == {"1", "2"}
    assert set(fake_imap.messages) == {"3"}
    calls = fake_imap.instances[0].calls
    assert ("select", '"transactions-pending"', False) in calls
    assert ("uid", "COPY", "1,2", '"transactions-processed"') in calls
    assert ("expunge",) in calls


def test_move_empty_list_does_not_touch_mailbox(fake_imap, config):
    _pending(fake_imap)
    with ImapLoader(config) as loader:
        loader.move([], "transactions-processed")
    assert [c[0] for c in fake_imap.instances[0].calls] == ["login", "logout"]
    assert len(fake_imap.messages) == 3


def test_move_to_missing_folder_keeps_messages(fake_imap, config):
    _pending(fake_imap, 1)
    with ImapLoader(config) as loader, pytest.raises(LoaderError, match="nowhere"):
        loader.move(["1"], "nowhere")
    assert set(fake_imap.messages) == {"1"}
    assert ("expunge",) not in fake_imap.instances[0].calls


def test_move_store_failure_is_loader_error(fake_imap, config):
    _pending(fake_imap, 1)
    fake_imap.store_status = "NO"
    with ImapLoader(config) as loader, pytest.raises(LoaderError, match="transactions-pending"):
        loader.move(["1"], "transactions-processed")


def test_move_imap_error_is_loader_error(fake_imap, config):
    _pending(fake_imap, 1)
    fake_imap.copy_error = True
    with ImapLoader(config) as loader, pytest.raises(LoaderError, match="transactions-processed"):
        loader.move(["1"], "transactions-processed")


def test_move_select_failure_is_loader_error(fake_imap, config):
    fake_imap.select_status = "NO"
    with ImapLoader(config) as loader, pytest.raises(LoaderError, match="transactions-pending"):
        loader.move(["1"], "transactions-processed")


def test_move_requires_connection(config):
    with pytest.raises(LoaderError, match="not connected"):
        ImapLoader(config).move(["1"], "transactions-processed")


SERVER_ERRORS = [imaplib.IMAP4.error("BAD command"), OSError("network down")]


def test_select_network_error_names_folder(fake_imap, config):
    fake_imap.errors = {("select", None): OSError("network down")}
    with ImapLoader(config) as loader, pytest.raises(LoaderError, match="transactions-pending"):
        loader.fetch_raw()


@pytest.mark.parametrize("error", SERVER_ERRORS)
def test_search_error_is_loader_error(fake_imap, config, error):
    fake_imap.errors = {("SEARCH", None): error}
    with ImapLoader(config) as loader, pytest.raises(LoaderError, match="transactions-pending") as exc:
        loader.fetch_raw()
    assert exc.value.__cause__ is error


def outcomes(results):
    return [(r is not None, u, d) for r, u, d in results]


ONLY_SECOND_NOT_DOWNLOADED = [(True, "1", True), (False, "2", False), (True, "3", True)]


def _fetch_calls(conn):
    return [c[2] for c in conn.calls if c[:2] == ("uid", "FETCH")]


def test_error_reply_fails_only_that_message_without_reconnecting(fake_imap, config, caplog):
    _pending(fake_imap)
    error = imaplib.IMAP4.error("BAD command")
    fake_imap.errors = {("FETCH", "2"): error}
    with ImapLoader(config) as loader:
        results = loader.fetch_raw()
    assert outcomes(results) == ONLY_SECOND_NOT_DOWNLOADED
    assert len(fake_imap.instances) == 1
    [record] = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert record.exc_info[1] is error
    assert "s3cret-pw" not in caplog.text


@pytest.mark.parametrize("error", [TimeoutError("timed out"), OSError("network down"),
                                   imaplib.IMAP4.abort("socket error: EOF")])
def test_broken_fetch_reconnects_and_abandons_old_connection(fake_imap, config, error):
    _pending(fake_imap)
    fake_imap.errors = {("FETCH", "2"): error}
    with ImapLoader(config) as loader:
        results = loader.fetch_raw()
        loader.move(["1", "3"], "transactions-processed")
    assert outcomes(results) == ONLY_SECOND_NOT_DOWNLOADED
    old, new = fake_imap.instances
    assert old.calls[-2:] == [("uid", "FETCH", "2", "(BODY.PEEK[])"), ("shutdown",)]
    assert ("select", '"transactions-pending"', True) in new.calls
    assert _fetch_calls(new) == ["3"]
    assert ("expunge",) in new.calls
    assert set(fake_imap.messages) == {"2"}


def test_broken_last_fetch_still_reconnects_for_move(fake_imap, config):
    _pending(fake_imap)
    fake_imap.drops = {("FETCH", "3")}
    with ImapLoader(config) as loader:
        loader.fetch_raw()
        loader.move(["1", "2"], "transactions-processed")
    assert len(fake_imap.instances) == 2
    assert set(fake_imap.messages) == {"3"}


def test_failing_shutdown_is_ignored(fake_imap, config, monkeypatch):
    def bad_shutdown(self):
        raise OSError("already closed")

    monkeypatch.setattr(fake_imap, "shutdown", bad_shutdown)
    _pending(fake_imap)
    fake_imap.drops = {("FETCH", "2")}
    with ImapLoader(config) as loader:
        assert outcomes(loader.fetch_raw()) == ONLY_SECOND_NOT_DOWNLOADED


@pytest.mark.parametrize("stage", ["connect", "login", "select"])
def test_reconnect_failure_is_loader_error(fake_imap, config, stage):
    _pending(fake_imap)
    fake_imap.drops = {("FETCH", "2")}
    fake_imap.reconnect_failure = stage
    with ImapLoader(config) as loader, pytest.raises(LoaderError) as exc:
        loader.fetch_raw()
    assert "s3cret-pw" not in str(exc.value)
    old = fake_imap.instances[0]
    assert old.calls[-1] == ("shutdown",)


def test_changed_uidvalidity_stops_fetch(fake_imap, config):
    _pending(fake_imap)
    fake_imap.drops = {("FETCH", "2")}
    fake_imap.uidvalidity = [b"1", b"2"]
    with ImapLoader(config) as loader, pytest.raises(LoaderError, match="identifiers changed"):
        loader.fetch_raw()
    assert _fetch_calls(fake_imap.instances[1]) == []


def test_unchanged_uidvalidity_continues(fake_imap, config):
    _pending(fake_imap)
    fake_imap.drops = {("FETCH", "2")}
    fake_imap.uidvalidity = [b"1"]
    with ImapLoader(config) as loader:
        assert outcomes(loader.fetch_raw()) == ONLY_SECOND_NOT_DOWNLOADED


def test_three_broken_fetches_in_a_row_stop_fetch(fake_imap, config):
    _pending(fake_imap, 4)
    fake_imap.drops = {("FETCH", "1"), ("FETCH", "2"), ("FETCH", "3")}
    with ImapLoader(config) as loader, pytest.raises(LoaderError, match="3 messages in a row"):
        loader.fetch_raw()
    assert len(fake_imap.instances) == 3  # no reconnect once the limit is reached
    assert [c for conn in fake_imap.instances for c in _fetch_calls(conn)] == ["1", "2", "3"]
    assert all(conn.calls[-1] == ("shutdown",) for conn in fake_imap.instances)


@pytest.mark.parametrize("between", [None, imaplib.IMAP4.error("BAD command")])
def test_separated_broken_fetches_do_not_stop_fetch(fake_imap, config, between):
    _pending(fake_imap, 5)
    fake_imap.drops = {("FETCH", "1"), ("FETCH", "3"), ("FETCH", "5")}
    if between:
        fake_imap.errors = {("FETCH", "2"): between, ("FETCH", "4"): between}
    with ImapLoader(config) as loader:
        assert len(loader.fetch_raw()) == 5


def test_connection_uses_timeout(fake_imap, config):
    with ImapLoader(config):
        pass
    assert fake_imap.instances[0].timeout == 30


@pytest.mark.parametrize("stage", ["connect", "login"])
def test_timeout_while_connecting_hides_password(fake_imap, config, monkeypatch, stage):
    def time_out(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(fake_imap, "__init__" if stage == "connect" else "login", time_out)
    with pytest.raises(LoaderError, match="could not log in") as exc:
        ImapLoader(config).__enter__()
    assert "s3cret-pw" not in str(exc.value)


@pytest.mark.parametrize("call", ["COPY", "STORE", "expunge"])
def test_move_network_error_names_destination(fake_imap, config, call):
    _pending(fake_imap, 1)
    fake_imap.errors = {(call, None): OSError("network down")}
    with ImapLoader(config) as loader, pytest.raises(LoaderError, match="transactions-processed"):
        loader.move(["1"], "transactions-processed")


def test_fake_broken_connection_rejects_later_commands_only_on_itself(fake_imap):
    fake_imap.drops = {("SEARCH", None)}
    old, new = fake_imap("h", 993), fake_imap("h", 993)
    for call in (lambda: old.uid("SEARCH", None, "ALL"), lambda: old.select("x"),
                 old.expunge, old.logout):
        with pytest.raises(imaplib.IMAP4.abort):
            call()
    assert new.select("x")[0] == "OK"
