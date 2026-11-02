import imaplib
import os
import socket
from pathlib import Path

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
    for name in ("CHEDDAR_IMAP_HOST", "CHEDDAR_IMAP_FOLDER"):
        monkeypatch.delenv(name, raising=False)


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


def test_refresh_does_not_modify_mailbox(client):
    FakeIMAP.messages = {"1": eml("chase/credit_card_transaction.eml")}
    client.post("/refresh_transactions")
    calls = FakeIMAP.instances[0].calls
    assert ("select", '"transactions-pending"', True) in calls
    assert not [c for c in calls if c[0] == "uid" and c[1] in ("STORE", "COPY", "MOVE")]


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
