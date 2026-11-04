import imaplib
import os
import socket
import sqlite3
from contextlib import closing
from pathlib import Path

import db
import main
import pytest
from fastapi.testclient import TestClient
from imap_fakes import FakeIMAP, build

FIXTURES = Path(__file__).parent.parent / "fixtures"
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


def eml(name):
    return (FIXTURES / name).read_bytes()


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


def test_refresh_mixed_batch(client):
    FakeIMAP.messages = {
        "1": eml("chase/credit_card_transaction.eml"),
        "2": eml("fidelity/investment_snapshot.eml"),
        "3": bytes(build(sender="Nobody <nobody@unknown.example>")),
    }
    response = client.post("/refresh_transactions")
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
    response = client.post("/refresh_transactions")
    assert response.status_code == 200
    assert response.json() == {"parsed_count": 0, "failed_count": 0, "parsed": [], "failed": []}


def test_refresh_moves_emails_to_processed_and_failed(client):
    FakeIMAP.messages = {
        "1": eml("chase/credit_card_transaction.eml"),
        "2": eml("fidelity/investment_snapshot.eml"),
        "3": bytes(build(sender="Nobody <nobody@unknown.example>")),
    }
    response = client.post("/refresh_transactions")
    assert response.status_code == 200
    assert set(FakeIMAP.folders["transactions-processed"]) == {"1", "2"}
    assert set(FakeIMAP.folders["transactions-failed"]) == {"3"}
    assert FakeIMAP.messages == {}


def test_refresh_empty_mailbox_does_not_modify_mailbox(client):
    client.post("/refresh_transactions")
    calls = FakeIMAP.instances[0].calls
    assert not [c for c in calls if c[0] == "uid" and c[1] in ("STORE", "COPY", "MOVE")]
    assert ("expunge",) not in calls


def test_second_refresh_has_nothing_to_reprocess(client):
    FakeIMAP.messages = {"1": eml("chase/credit_card_transaction.eml")}
    assert client.post("/refresh_transactions").json()["parsed_count"] == 1
    assert client.post("/refresh_transactions").json() == {
        "parsed_count": 0, "failed_count": 0, "parsed": [], "failed": []}


def test_refresh_uses_configured_destination_folders(client, monkeypatch):
    monkeypatch.setenv("CHEDDAR_IMAP_PROCESSED_FOLDER", "done")
    FakeIMAP.folders["done"] = {}
    FakeIMAP.messages = {"1": eml("chase/credit_card_transaction.eml")}
    assert client.post("/refresh_transactions").status_code == 200
    assert set(FakeIMAP.folders["done"]) == {"1"}


def test_missing_destination_folder_is_502(client):
    del FakeIMAP.folders["transactions-processed"]
    FakeIMAP.messages = {"1": eml("chase/credit_card_transaction.eml")}
    response = client.post("/refresh_transactions")
    assert response.status_code == 502
    assert "transactions-processed" in response.json()["detail"]
    assert set(FakeIMAP.messages) == {"1"}


def test_missing_config_is_500(client, monkeypatch):
    monkeypatch.delenv("CHEDDAR_IMAP_PASSWORD")
    response = client.post("/refresh_transactions")
    assert response.status_code == 500
    assert "CHEDDAR_IMAP_PASSWORD" in response.json()["detail"]
    assert PASSWORD not in response.text
    assert FakeIMAP.instances == []


def test_login_failure_is_502(client):
    FakeIMAP.login_error = True
    response = client.post("/refresh_transactions")
    assert response.status_code == 502
    assert PASSWORD not in response.text


def test_select_failure_is_502(client):
    FakeIMAP.select_status = "NO"
    response = client.post("/refresh_transactions")
    assert response.status_code == 502
    assert "transactions-pending" in response.json()["detail"]


def test_search_failure_is_502(client, monkeypatch):
    monkeypatch.setattr(FakeIMAP, "uid", lambda self, command, *args: ("NO", []))
    response = client.post("/refresh_transactions")
    assert response.status_code == 502
    assert "search failed" in response.json()["detail"]


def test_concurrent_refresh_is_409(client):
    assert main._refresh_lock.acquire(blocking=False)
    try:
        response = client.post("/refresh_transactions")
    finally:
        main._refresh_lock.release()
    assert response.status_code == 409
    assert FakeIMAP.instances == []  # no second mailbox session


def test_lock_released_after_success_and_errors(client, monkeypatch):
    assert client.post("/refresh_transactions").status_code == 200

    monkeypatch.delenv("CHEDDAR_IMAP_PASSWORD")
    assert client.post("/refresh_transactions").status_code == 500
    monkeypatch.setenv("CHEDDAR_IMAP_PASSWORD", PASSWORD)
    assert client.post("/refresh_transactions").status_code == 200

    FakeIMAP.login_error = True
    assert client.post("/refresh_transactions").status_code == 502
    FakeIMAP.login_error = False
    assert client.post("/refresh_transactions").status_code == 200
    assert not main._refresh_lock.locked()


def test_refresh_saves_results_to_database(client, database):
    FakeIMAP.messages = {
        "1": eml("chase/credit_card_transaction.eml"),
        "2": eml("fidelity/investment_snapshot.eml"),
    }
    positions = client.post("/refresh_transactions").json()["parsed"][1]["result"]["positions"]
    assert query(database, "SELECT count(*) FROM transactions") == [(1,)]
    assert query(database, "SELECT count(*) FROM investment_positions") == [(len(positions),)]


def test_transaction_records_source_message_id(client, database):
    FakeIMAP.messages = {"1": eml("chase/credit_card_transaction.eml")}
    client.post("/refresh_transactions")
    [(source,)] = query(database, "SELECT source_email_id FROM transactions")
    assert source.startswith("<") or source == "1"
    assert source in FakeIMAP.folders["transactions-processed"]["1"].decode()


def test_only_failed_emails_save_nothing(client, database):
    FakeIMAP.messages = {"1": bytes(build(sender="Nobody <nobody@unknown.example>"))}
    assert client.post("/refresh_transactions").status_code == 200
    assert query(database, "SELECT count(*) FROM transactions") == [(0,)]
    assert set(FakeIMAP.folders["transactions-failed"]) == {"1"}


def test_database_failure_is_500_and_moves_nothing(client, database, monkeypatch):
    FakeIMAP.messages = {
        "1": eml("chase/credit_card_transaction.eml"),
        "2": eml("fidelity/investment_snapshot.eml"),
    }
    real = db.save_position_summary

    def boom(conn, summary):
        real(conn, summary)
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(db, "save_position_summary", boom)
    response = client.post("/refresh_transactions")
    assert response.status_code == 500
    assert "database" in response.json()["detail"]
    assert query(database, "SELECT count(*) FROM transactions") == [(0,)]
    assert query(database, "SELECT count(*) FROM investment_positions") == [(0,)]
    assert set(FakeIMAP.messages) == {"1", "2"}
    assert FakeIMAP.folders["transactions-processed"] == {}
    assert not main._refresh_lock.locked()


def test_unusable_database_path_is_500(client, tmp_path, monkeypatch):
    monkeypatch.setenv("CHEDDAR_DB_PATH", str(tmp_path / "missing-dir" / "x.db"))
    FakeIMAP.messages = {"1": eml("chase/credit_card_transaction.eml")}
    assert client.post("/refresh_transactions").status_code == 500
    assert set(FakeIMAP.messages) == {"1"}


def test_retry_after_database_failure_saves_and_moves(client, database, monkeypatch):
    FakeIMAP.messages = {"1": eml("chase/credit_card_transaction.eml")}
    with monkeypatch.context() as m:
        m.setattr(db, "save_transaction",
                  lambda *args: (_ for _ in ()).throw(sqlite3.OperationalError("locked")))
        assert client.post("/refresh_transactions").status_code == 500
    assert client.post("/refresh_transactions").status_code == 200
    assert query(database, "SELECT count(*) FROM transactions") == [(1,)]
    assert set(FakeIMAP.folders["transactions-processed"]) == {"1"}


def test_retry_after_failed_move_does_not_duplicate(client, database):
    FakeIMAP.messages = {"1": eml("chase/credit_card_transaction.eml")}
    del FakeIMAP.folders["transactions-processed"]
    assert client.post("/refresh_transactions").status_code == 502
    assert query(database, "SELECT count(*) FROM transactions") == [(1,)]
    assert set(FakeIMAP.messages) == {"1"}

    FakeIMAP.folders["transactions-processed"] = {}
    assert client.post("/refresh_transactions").status_code == 200
    assert query(database, "SELECT count(*) FROM transactions") == [(1,)]
    assert FakeIMAP.messages == {}
