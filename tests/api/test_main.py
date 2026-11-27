import imaplib
import os
import socket
import sqlite3
from contextlib import closing

import db
import main
import pytest
from case_files import case_eml
from fastapi.testclient import TestClient
from imap_fakes import FakeIMAP, build

USER, PASSWORD = "me@example.com", "s3cret-pw"


@pytest.fixture(autouse=True)
def no_live_imap(fake_imap, monkeypatch):
    """Every API test runs against FakeIMAP with dummy credentials.

    Any attempt to open a real socket fails loudly, and credentials from the
    developer's shell are replaced so they can never be used.
    """
    def refuse(*args, **kwargs):
        raise AssertionError("live network call in test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setenv("CHEDDAR_IMAP_USER", USER)
    monkeypatch.setenv("CHEDDAR_IMAP_PASSWORD", PASSWORD)
    for name in ("CHEDDAR_IMAP_HOST", "CHEDDAR_IMAP_FOLDER",
                 "CHEDDAR_IMAP_PROCESSED_FOLDER", "CHEDDAR_IMAP_FAILED_FOLDER"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    """Every API test writes to a throwaway database, never a real one."""
    path = tmp_path / "test.db"
    monkeypatch.setenv("CHEDDAR_DB_PATH", str(path))
    return path


def query(path, sql):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(sql).fetchall()


@pytest.fixture
def client():
    return TestClient(main.app)


def test_no_live_imap_and_dummy_credentials():
    assert imaplib.IMAP4_SSL is FakeIMAP
    assert os.environ["CHEDDAR_IMAP_USER"] == USER
    with socket.socket() as sock, pytest.raises(AssertionError, match="live network call"):
        sock.connect(("127.0.0.1", 1))


def test_health_needs_no_credentials(client, monkeypatch):
    monkeypatch.delenv("CHEDDAR_IMAP_USER")
    monkeypatch.delenv("CHEDDAR_IMAP_PASSWORD")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert FakeIMAP.instances == []


def test_old_refresh_path_is_404(client):
    assert client.post("/refresh_transactions").status_code == 404
    assert FakeIMAP.instances == []


def test_refresh_mixed_batch(client):
    FakeIMAP.messages = {
        "1": case_eml("chase/card_alert"),
        "2": case_eml("fidelity/position_summary"),
        "3": bytes(build(sender="Nobody <nobody@unknown.example>")),
    }
    response = client.post("/refresh")
    assert response.status_code == 200
    body = response.json()
    assert body["parsed_count"] == 2
    assert body["failed_count"] == 1
    by_uid = {item["uid"]: item["result"] for item in body["parsed"]}
    assert by_uid["1"]["type"] == "transaction"
    assert isinstance(by_uid["1"]["amount"], str)  # Decimal serialized
    assert by_uid["2"]["type"] == "position_summary"
    assert by_uid["2"]["positions"]
    assert body["failed"][0]["uid"] == "3"
    assert body["failed"][0]["reason"]


def test_refresh_empty_mailbox(client):
    response = client.post("/refresh")
    assert response.status_code == 200
    assert response.json() == {"parsed_count": 0, "failed_count": 0, "parsed": [], "failed": []}


def test_refresh_moves_emails_to_processed_and_failed(client):
    FakeIMAP.messages = {
        "1": case_eml("chase/card_alert"),
        "2": case_eml("fidelity/position_summary"),
        "3": bytes(build(sender="Nobody <nobody@unknown.example>")),
    }
    response = client.post("/refresh")
    assert response.status_code == 200
    assert set(FakeIMAP.folders["transactions-processed"]) == {"1", "2"}
    assert set(FakeIMAP.folders["transactions-failed"]) == {"3"}
    assert FakeIMAP.messages == {}


def test_refresh_empty_mailbox_does_not_modify_mailbox(client):
    client.post("/refresh")
    calls = FakeIMAP.instances[0].calls
    assert not [c for c in calls if c[0] == "uid" and c[1] in ("STORE", "COPY", "MOVE")]
    assert ("expunge",) not in calls


def test_second_refresh_has_nothing_to_reprocess(client):
    FakeIMAP.messages = {"1": case_eml("chase/card_alert")}
    assert client.post("/refresh").json()["parsed_count"] == 1
    assert client.post("/refresh").json() == {
        "parsed_count": 0, "failed_count": 0, "parsed": [], "failed": []}


def test_refresh_uses_configured_destination_folders(client, monkeypatch):
    monkeypatch.setenv("CHEDDAR_IMAP_PROCESSED_FOLDER", "done")
    FakeIMAP.folders["done"] = {}
    FakeIMAP.messages = {"1": case_eml("chase/card_alert")}
    assert client.post("/refresh").status_code == 200
    assert set(FakeIMAP.folders["done"]) == {"1"}


def test_missing_destination_folder_is_502(client):
    del FakeIMAP.folders["transactions-processed"]
    FakeIMAP.messages = {"1": case_eml("chase/card_alert")}
    response = client.post("/refresh")
    assert response.status_code == 502
    assert "transactions-processed" in response.json()["detail"]
    assert set(FakeIMAP.messages) == {"1"}


def test_missing_config_is_500(client, monkeypatch):
    monkeypatch.delenv("CHEDDAR_IMAP_PASSWORD")
    response = client.post("/refresh")
    assert response.status_code == 500
    assert "CHEDDAR_IMAP_PASSWORD" in response.json()["detail"]
    assert PASSWORD not in response.text
    assert FakeIMAP.instances == []


def test_login_failure_is_502(client):
    FakeIMAP.login_error = True
    response = client.post("/refresh")
    assert response.status_code == 502
    assert PASSWORD not in response.text


def test_select_failure_is_502(client):
    FakeIMAP.select_status = "NO"
    response = client.post("/refresh")
    assert response.status_code == 502
    assert "transactions-pending" in response.json()["detail"]


def test_search_failure_is_502(client, monkeypatch):
    monkeypatch.setattr(FakeIMAP, "uid", lambda self, command, *args: ("NO", []))
    response = client.post("/refresh")
    assert response.status_code == 502
    assert "search failed" in response.json()["detail"]


def three_emails():
    return {
        "1": case_eml("chase/card_alert"),
        "2": case_eml("capital_one/purchase_alert"),
        "3": case_eml("american_express/large_purchase"),
    }


def assert_nothing_moved():
    assert set(FakeIMAP.messages) == {"1", "2", "3"}
    assert FakeIMAP.folders == {"transactions-processed": {}, "transactions-failed": {}}


def assert_only_second_left_pending(response, database):
    assert response.status_code == 200
    body = response.json()
    assert [item["uid"] for item in body["parsed"]] == ["1", "3"]
    assert body["failed"] == [{"uid": "2", "reason": "message could not be downloaded"}]
    assert body["failed_count"] == 1
    assert query(database, "SELECT count(*) FROM transactions") == [(2,)]
    assert set(FakeIMAP.folders["transactions-processed"]) == {"1", "3"}
    assert FakeIMAP.folders["transactions-failed"] == {}
    assert set(FakeIMAP.messages) == {"2"}


def test_fetch_error_reply_leaves_email_pending_and_next_refresh_retries(client, database):
    FakeIMAP.messages = three_emails()
    FakeIMAP.errors = {("FETCH", "2"): imaplib.IMAP4.error("BAD fetch")}
    assert_only_second_left_pending(client.post("/refresh"), database)

    assert client.post("/refresh").json()["parsed_count"] == 1
    assert query(database, "SELECT count(*) FROM transactions") == [(3,)]
    assert set(FakeIMAP.folders["transactions-processed"]) == {"1", "2", "3"}
    assert FakeIMAP.messages == {}


@pytest.mark.parametrize("reply", [("NO", [None]), ("OK", [b")"])])
def test_fetch_without_message_leaves_email_pending(client, database, monkeypatch, reply):
    FakeIMAP.messages = three_emails()
    real = FakeIMAP.uid

    def uid(self, command, *args):
        if command == "FETCH" and args[0] == "2":
            return reply
        return real(self, command, *args)

    monkeypatch.setattr(FakeIMAP, "uid", uid)
    assert_only_second_left_pending(client.post("/refresh"), database)


def test_broken_fetch_reconnects_and_leaves_email_pending(client, database):
    FakeIMAP.messages = three_emails()
    FakeIMAP.drops = {("FETCH", "2")}
    assert_only_second_left_pending(client.post("/refresh"), database)
    assert len(FakeIMAP.instances) == 2


def test_undecodable_email_moves_to_failed(client):
    FakeIMAP.messages = {"1": b"From: a@b.com\r\n\r\nno date"}
    body = client.post("/refresh").json()
    assert body["failed"] == [{"uid": "1", "reason": "message could not be decoded"}]
    assert set(FakeIMAP.folders["transactions-failed"]) == {"1"}


@pytest.mark.parametrize("drops, reconnect_failure", [
    ({("FETCH", "1")}, "connect"),
    ({("FETCH", "2")}, "connect"),
    ({("FETCH", "2")}, "login"),
    ({("FETCH", "1"), ("FETCH", "2"), ("FETCH", "3")}, None),
])
def test_stopped_fetch_is_502_saves_and_moves_nothing(client, database, drops, reconnect_failure):
    FakeIMAP.messages = three_emails()
    FakeIMAP.drops = set(drops)
    FakeIMAP.reconnect_failure = reconnect_failure
    response = client.post("/refresh")
    assert response.status_code == 502
    assert PASSWORD not in response.text
    assert not database.exists() or query(database, "SELECT count(*) FROM transactions") == [(0,)]
    assert_nothing_moved()

    FakeIMAP.instances, FakeIMAP.drops, FakeIMAP.reconnect_failure = [], set(), None
    assert client.post("/refresh").status_code == 200
    assert query(database, "SELECT count(*) FROM transactions") == [(3,)]
    assert FakeIMAP.messages == {}


def test_connection_error_during_move_keeps_saved_rows(client, database):
    FakeIMAP.messages = three_emails()
    FakeIMAP.errors = {("COPY", None): OSError("network down")}
    response = client.post("/refresh")
    assert response.status_code == 502
    assert PASSWORD not in response.text
    assert query(database, "SELECT count(*) FROM transactions") == [(3,)]
    assert_nothing_moved()

    assert client.post("/refresh").status_code == 200
    assert query(database, "SELECT count(*) FROM transactions") == [(3,)]
    assert FakeIMAP.messages == {}


def test_concurrent_refresh_is_409(client):
    assert main._refresh_lock.acquire(blocking=False)
    try:
        response = client.post("/refresh")
    finally:
        main._refresh_lock.release()
    assert response.status_code == 409
    assert FakeIMAP.instances == []  # no second mailbox session


def test_lock_released_after_success_and_errors(client, monkeypatch):
    assert client.post("/refresh").status_code == 200

    monkeypatch.delenv("CHEDDAR_IMAP_PASSWORD")
    assert client.post("/refresh").status_code == 500
    monkeypatch.setenv("CHEDDAR_IMAP_PASSWORD", PASSWORD)
    assert client.post("/refresh").status_code == 200

    FakeIMAP.login_error = True
    assert client.post("/refresh").status_code == 502
    FakeIMAP.login_error = False
    assert client.post("/refresh").status_code == 200
    assert not main._refresh_lock.locked()


def test_refresh_saves_results_to_database(client, database):
    FakeIMAP.messages = {
        "1": case_eml("chase/card_alert"),
        "2": case_eml("fidelity/position_summary"),
    }
    positions = client.post("/refresh").json()["parsed"][1]["result"]["positions"]
    assert query(database, "SELECT count(*) FROM transactions") == [(1,)]
    assert query(database, "SELECT count(*) FROM investment_positions") == [(len(positions),)]


def test_transaction_records_source_message_id(client, database):
    FakeIMAP.messages = {"1": case_eml("chase/card_alert")}
    client.post("/refresh")
    [(source,)] = query(database, "SELECT source_email_id FROM transactions")
    assert source.startswith("<") or source == "1"
    assert source in FakeIMAP.folders["transactions-processed"]["1"].decode()


def test_only_failed_emails_save_nothing(client, database):
    FakeIMAP.messages = {"1": bytes(build(sender="Nobody <nobody@unknown.example>"))}
    assert client.post("/refresh").status_code == 200
    assert query(database, "SELECT count(*) FROM transactions") == [(0,)]
    assert set(FakeIMAP.folders["transactions-failed"]) == {"1"}


def test_database_failure_is_500_and_moves_nothing(client, database, monkeypatch):
    FakeIMAP.messages = {
        "1": case_eml("chase/card_alert"),
        "2": case_eml("fidelity/position_summary"),
    }
    real = db.save_position_summary

    def boom(conn, summary):
        real(conn, summary)
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(db, "save_position_summary", boom)
    response = client.post("/refresh")
    assert response.status_code == 500
    assert "database" in response.json()["detail"]
    assert query(database, "SELECT count(*) FROM transactions") == [(0,)]
    assert query(database, "SELECT count(*) FROM investment_positions") == [(0,)]
    assert set(FakeIMAP.messages) == {"1", "2"}
    assert FakeIMAP.folders["transactions-processed"] == {}
    assert not main._refresh_lock.locked()


def test_unusable_database_path_is_500(client, tmp_path, monkeypatch):
    monkeypatch.setenv("CHEDDAR_DB_PATH", str(tmp_path / "missing-dir" / "x.db"))
    FakeIMAP.messages = {"1": case_eml("chase/card_alert")}
    assert client.post("/refresh").status_code == 500
    assert set(FakeIMAP.messages) == {"1"}


def test_retry_after_database_failure_saves_and_moves(client, database, monkeypatch):
    FakeIMAP.messages = {"1": case_eml("chase/card_alert")}
    with monkeypatch.context() as m:
        m.setattr(db, "save_transaction",
                  lambda *args: (_ for _ in ()).throw(sqlite3.OperationalError("locked")))
        assert client.post("/refresh").status_code == 500
    assert client.post("/refresh").status_code == 200
    assert query(database, "SELECT count(*) FROM transactions") == [(1,)]
    assert set(FakeIMAP.folders["transactions-processed"]) == {"1"}


def test_retry_after_failed_move_does_not_duplicate(client, database):
    FakeIMAP.messages = {"1": case_eml("chase/card_alert")}
    del FakeIMAP.folders["transactions-processed"]
    assert client.post("/refresh").status_code == 502
    assert query(database, "SELECT count(*) FROM transactions") == [(1,)]
    assert set(FakeIMAP.messages) == {"1"}

    FakeIMAP.folders["transactions-processed"] = {}
    assert client.post("/refresh").status_code == 200
    assert query(database, "SELECT count(*) FROM transactions") == [(1,)]
    assert FakeIMAP.messages == {}


def seed_transactions(database, count=3):
    from decimal import Decimal

    from email_parser.parsing.models import Transaction

    with closing(db.connect(str(database))) as conn, conn:
        for n in range(count):
            db.save_transaction(
                conn, Transaction(f"M{n}", Decimal("-1.50"), "Chase 1234", "2026-10-29T22:01:51+00:00"),
                f"<{n}@x>")


def listed_ids(client, **params):
    response = client.get("/transactions", params=params)
    assert response.status_code == 200
    return [t["id"] for t in response.json()["transactions"]]


def delete(client, body):
    return client.request("DELETE", "/transactions", json=body)


def test_list_empty_database(client):
    assert client.get("/transactions").json() == {"transactions": []}


def test_list_active_and_deleted(client, database):
    seed_transactions(database)
    assert delete(client, {"ids": [2]}).status_code == 200
    assert listed_ids(client) == [1, 3]
    assert listed_ids(client, deleted="true") == [2]
    [item] = client.get("/transactions", params={"deleted": "true"}).json()["transactions"]
    assert item["original_merchant"] == "M1"
    assert item["original_amount"] == "-1.50"
    assert item["deleted_at"] is not None


def test_list_shows_tags(client, database):
    seed_transactions(database, 1)
    with closing(sqlite3.connect(database)) as conn, conn:
        conn.executemany("INSERT INTO transaction_tags VALUES (1, ?)",
                         [("vacation",), ("shared",)])
    [item] = client.get("/transactions").json()["transactions"]
    assert item["tags"] == ["shared", "vacation"]
    assert item["deleted_at"] is None


def test_delete_transactions(client, database):
    seed_transactions(database)
    response = delete(client, {"ids": [1, 2]})
    assert response.status_code == 200
    assert response.json() == {"deleted": [1, 2], "not_found": []}
    assert listed_ids(client) == [3]
    assert query(database, "SELECT count(*) FROM transactions") == [(3,)]


def test_delete_reports_missing_ids(client, database):
    seed_transactions(database, 1)
    assert delete(client, {"ids": [1, 9999]}).json() == {"deleted": [1], "not_found": [9999]}


def test_delete_already_deleted_id_is_not_found(client, database):
    seed_transactions(database, 1)
    delete(client, {"ids": [1]})
    [(first,)] = query(database, "SELECT deleted_at FROM transactions")
    assert delete(client, {"ids": [1]}).json() == {"deleted": [], "not_found": [1]}
    assert query(database, "SELECT deleted_at FROM transactions") == [(first,)]


def test_delete_duplicate_ids(client, database):
    seed_transactions(database, 1)
    assert delete(client, {"ids": [1, 1, 7, 7]}).json() == {"deleted": [1], "not_found": [7]}


def test_delete_empty_list(client):
    assert delete(client, {"ids": []}).json() == {"deleted": [], "not_found": []}


@pytest.mark.parametrize("body", [{"ids": ["a"]}, {}, {"ids": 1}])
def test_delete_invalid_body_is_422(client, database, body):
    seed_transactions(database, 1)
    assert delete(client, body).status_code == 422
    assert listed_ids(client) == [1]


def test_delete_without_body_is_422(client):
    assert client.request("DELETE", "/transactions").status_code == 422


def test_delete_during_refresh_is_not_blocked(client, database):
    seed_transactions(database, 1)
    assert main._refresh_lock.acquire(blocking=False)
    try:
        response = delete(client, {"ids": [1]})
    finally:
        main._refresh_lock.release()
    assert response.status_code == 200


def test_list_database_failure_is_500(client, monkeypatch):
    def boom(conn, deleted, **filters):
        raise sqlite3.OperationalError("disk error")

    monkeypatch.setattr(db, "list_transactions", boom)
    response = client.get("/transactions")
    assert response.status_code == 500
    assert "database" in response.json()["detail"]


def test_delete_database_failure_is_500_and_changes_nothing(client, database, monkeypatch):
    seed_transactions(database, 2)
    real = db.soft_delete_transactions

    def boom(conn, ids):
        real(conn, ids)
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(db, "soft_delete_transactions", boom)
    response = delete(client, {"ids": [1, 2]})
    assert response.status_code == 500
    assert "database" in response.json()["detail"]
    assert query(database, "SELECT count(*) FROM transactions WHERE deleted_at IS NULL") == [(2,)]


def test_refresh_does_not_reimport_deleted_transaction(client, database):
    FakeIMAP.messages = {"1": case_eml("chase/card_alert")}
    client.post("/refresh")
    assert listed_ids(client) == [1]
    delete(client, {"ids": [1]})
    FakeIMAP.messages = {"1": case_eml("chase/card_alert")}
    assert client.post("/refresh").status_code == 200
    assert query(database, "SELECT count(*) FROM transactions") == [(1,)]
    assert listed_ids(client) == []
    assert listed_ids(client, deleted="true") == [1]


def patch(client, transaction_id, body):
    return client.patch(f"/transactions/{transaction_id}", json=body)


def stored(client, **params):
    return client.get("/transactions", params=params).json()["transactions"]


def test_list_unedited_merchant_and_amount(client, database):
    seed_transactions(database, 1)
    [item] = stored(client)
    assert (item["merchant"], item["amount"]) == ("M0", "-1.50")


def test_update_fields_leaves_others_unchanged(client, database):
    seed_transactions(database, 2)
    before = stored(client)
    changes = {"category": " Travel ", "transaction_type": "Expense", "tags": ["work"]}
    response = patch(client, 1, changes)
    assert response.status_code == 200
    expected = {**before[0], **changes, "category": "Travel"}
    assert response.json() == expected
    assert stored(client) == [expected, before[1]]


def test_update_merchant_and_amount_then_revert(client, database):
    seed_transactions(database, 1)
    body = patch(client, 1, {"merchant": "Uber", "amount": "-15.00", "category": "Travel",
                             "transaction_type": "Income"}).json()
    assert (body["merchant"], body["amount"]) == ("Uber", "-15.00")
    assert (body["original_merchant"], body["original_amount"]) == ("M0", "-1.50")
    body = patch(client, 1, {"merchant": None, "amount": None, "category": None,
                             "transaction_type": None}).json()
    assert (body["merchant"], body["amount"]) == ("M0", "-1.50")
    assert body["category"] is None and body["transaction_type"] is None
    assert query(database, "SELECT merchant, amount FROM transactions") == [(None, None)]


@pytest.mark.parametrize("amount, expected", [
    ("0", "0"), ("1E+3", "1000"), ("1e-7", "0.0000001"), (-12.25, "-12.25"),
    ("12345678901234567890", "12345678901234567890"),
])
def test_update_amount_is_plain_notation(client, database, amount, expected):
    seed_transactions(database, 1)
    assert patch(client, 1, {"amount": amount}).json()["amount"] == expected


def test_update_empty_merchant_is_kept(client, database):
    seed_transactions(database, 1)
    assert patch(client, 1, {"merchant": ""}).json()["merchant"] == ""


def test_update_replaces_and_clears_tags(client, database):
    seed_transactions(database, 1)
    patch(client, 1, {"tags": ["a", "b"]})
    assert patch(client, 1, {"tags": [" c ", "c"]}).json()["tags"] == ["c"]
    assert patch(client, 1, {"category": "X"}).json()["tags"] == ["c"]
    assert patch(client, 1, {"tags": []}).json()["tags"] == []


def test_update_empty_object_changes_nothing(client, database):
    seed_transactions(database, 1)
    [before] = stored(client)
    response = patch(client, 1, {})
    assert response.status_code == 200
    assert response.json() == before


@pytest.mark.parametrize("field", [
    "id", "original_merchant", "original_amount", "transaction_timestamp", "account",
    "deleted_at", "source_email_id", "unknown",
])
def test_update_protected_or_unknown_field_is_422(client, database, field):
    seed_transactions(database, 1)
    [before] = stored(client)
    assert patch(client, 1, {"category": "Travel", field: "1"}).status_code == 422
    assert stored(client) == [before]


@pytest.mark.parametrize("body", [
    {"transaction_type": "Transfer"}, {"amount": "abc"}, {"amount": "NaN"},
    {"amount": "Infinity"}, {"amount": "1e999999999"}, {"amount": "1e-999999999"},
    {"amount": "123456789012345678901"}, {"category": "  "}, {"merchant": 5},
    {"tags": None}, {"tags": [""]}, {"tags": [None]}, {"tags": "a"}, [], "x", None,
])
def test_update_invalid_body_is_422(client, database, body):
    seed_transactions(database, 1)
    [before] = stored(client)
    assert patch(client, 1, body).status_code == 422
    assert stored(client) == [before]


@pytest.mark.parametrize("body", [
    r'''{"category": "X", "merchant": "\ud800"}''', r'''{"category": "\ud800"}''',
    r'''{"category": "X", "tags": ["ok", "\ud800"]}''',
])
def test_update_unpaired_surrogate_is_422_and_changes_nothing(client, database, body):
    seed_transactions(database, 1)
    patch(client, 1, {"tags": ["old"]})
    [before] = stored(client)
    response = client.patch(
        "/transactions/1", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json() == {"detail": "text must be valid Unicode"}
    assert stored(client) == [before]


def test_delete_unpaired_surrogate_is_422(client, database):
    seed_transactions(database, 1)
    response = client.request(
        "DELETE", "/transactions", content=r'''{"ids": ["\ud800"]}''',
        headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json() == {"detail": "text must be valid Unicode"}
    assert listed_ids(client) == [1]


@pytest.mark.parametrize("transaction_id", ["abc", "0", "-1", str(2**63)])
def test_update_invalid_id_is_422(client, transaction_id):
    assert patch(client, transaction_id, {}).status_code == 422


@pytest.mark.parametrize("transaction_id", [9999, 2**63 - 1])
def test_update_unknown_id_is_404(client, database, transaction_id):
    seed_transactions(database, 1)
    response = patch(client, transaction_id, {"tags": ["a"]})
    assert response.status_code == 404
    assert response.json() == {"detail": "transaction not found"}


def test_update_deleted_transaction_is_404(client, database):
    seed_transactions(database, 1)
    delete(client, {"ids": [1]})
    [before] = stored(client, deleted="true")
    assert patch(client, 1, {"category": "X", "tags": ["a"]}).status_code == 404
    assert stored(client, deleted="true") == [before]


def test_update_database_failure_is_500_and_changes_nothing(client, database, monkeypatch):
    seed_transactions(database, 1)
    [before] = stored(client)
    real = db.update_transaction

    def boom(*args):
        real(*args)
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(db, "update_transaction", boom)
    response = patch(client, 1, {"category": "X", "tags": ["a"]})
    assert response.status_code == 500
    assert response.json() == {"detail": "could not update the transaction in the database"}
    assert stored(client) == [before]


def test_update_during_refresh_is_not_blocked(client, database):
    seed_transactions(database, 1)
    assert main._refresh_lock.acquire(blocking=False)
    try:
        response = patch(client, 1, {"category": "X"})
    finally:
        main._refresh_lock.release()
    assert response.status_code == 200


def test_edits_survive_refresh_of_same_email(client):
    FakeIMAP.messages = {"1": case_eml("chase/card_alert")}
    client.post("/refresh")
    edited = patch(client, 1, {"merchant": "Mine", "amount": "-1", "category": "C",
                               "transaction_type": "Expense", "tags": ["t"]}).json()
    FakeIMAP.messages = {"1": case_eml("chase/card_alert")}
    assert client.post("/refresh").status_code == 200
    assert stored(client) == [edited]


def test_list_filters(client, database):
    seed_transactions(database)
    patch(client, 1, {"category": "Travel", "transaction_type": "Expense",
                      "tags": ["work", "shared"]})
    patch(client, 2, {"category": "Food", "transaction_type": "Income",
                      "tags": ["shared"], "merchant": "Joe's Diner"})
    assert listed_ids(client, merchant="diner") == [2]
    assert listed_ids(client, merchant="m1") == []
    assert listed_ids(client, merchant=["m0", "m2"]) == [1, 3]
    assert listed_ids(client, merchant="%") == []
    assert listed_ids(client, category="travel") == [1]
    assert listed_ids(client, category=["travel", "food"]) == [1, 2]
    assert listed_ids(client, account="chase 1234") == [1, 2, 3]
    assert listed_ids(client, account="Chase") == []
    assert listed_ids(client, tag=["work", "shared"]) == [1, 2]
    assert listed_ids(client, transaction_type="Income") == [2]
    assert listed_ids(client, transaction_type=["Income", "Expense"]) == [1, 2]
    assert listed_ids(client, category="travel", transaction_type="Expense") == [1]
    assert listed_ids(client, category="travel", transaction_type="Income") == []
    [item] = stored(client, tag="work")
    assert item["tags"] == ["shared", "work"]


def test_list_date_filters(client, database):
    seed_transactions(database, 1)  # dated 2026-10-29
    assert listed_ids(client, start_date="2026-10-29", end_date="2026-10-29") == [1]
    assert listed_ids(client, start_date="2026-10-30") == []
    assert listed_ids(client, end_date="2026-10-28") == []


def test_list_filters_with_deleted(client, database):
    seed_transactions(database)
    delete(client, {"ids": [2]})
    assert listed_ids(client, deleted="true", account="Chase 1234") == [2]
    assert listed_ids(client, account="Chase 1234") == [1, 3]


@pytest.mark.parametrize("params", [
    {"deleted": "maybe"}, {"start_date": "yesterday"}, {"start_date": ""},
    {"start_date": "86400"}, {"end_date": "2026-10-29T00:00:00"},
    {"end_date": "2026-02-30"}, {"transaction_type": "Transfer"},
    {"transaction_type": "income"}, {"merchant": ""}, {"category": "  "},
    {"account": ""}, {"tag": ["ok", ""]},
])
def test_list_invalid_filter_is_422(client, params):
    assert client.get("/transactions", params=params).status_code == 422


def test_list_reversed_date_range_is_422(client):
    response = client.get(
        "/transactions", params={"start_date": "2026-11-02", "end_date": "2026-11-01"})
    assert response.status_code == 422
    assert response.json() == {"detail": "start_date must not be after end_date"}
