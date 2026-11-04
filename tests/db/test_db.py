import sqlite3
from contextlib import closing
from decimal import Decimal

import db
import pytest
from email_parser.parsing.models import InvestmentPosition, PositionSummary, Transaction


@pytest.fixture
def conn(tmp_path):
    with closing(db.connect(str(tmp_path / "t.db"))) as c:
        yield c


def tx(merchant="Trader Joe's", amount="-23.45", account="Chase 1234",
       timestamp="2026-10-29T22:01:51+00:00"):
    return Transaction(merchant, Decimal(amount), account, timestamp)


def pos(ticker="VTI", price="250.10", quantity="10.5000", date="2026-10-29"):
    return InvestmentPosition(ticker, Decimal(quantity), Decimal(price), Decimal("2626.05"),
                              "Fidelity 5678", "Brokerage", date)


def rows(conn, sql):
    return conn.execute(sql).fetchall()


def test_db_path_default_and_custom():
    assert db.db_path({}) == "./cheddar.db"
    assert db.db_path({"CHEDDAR_DB_PATH": ""}) == "./cheddar.db"
    assert db.db_path({"CHEDDAR_DB_PATH": "/data/money.db"}) == "/data/money.db"


def test_db_path_reads_process_environment(monkeypatch):
    monkeypatch.setenv("CHEDDAR_DB_PATH", "/x/y.db")
    assert db.db_path() == "/x/y.db"


def test_first_use_creates_file_and_tables(tmp_path):
    path = tmp_path / "new.db"
    with closing(db.connect(str(path))) as c:
        names = {r[0] for r in rows(c, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert path.exists()
    assert {"transactions", "transaction_tags", "investment_positions"} <= names


def test_existing_rows_survive_reopen(tmp_path):
    path = str(tmp_path / "t.db")
    with closing(db.connect(path)) as c, c:
        db.save_transaction(c, tx(), "<a@x>")
    with closing(db.connect(path)) as c:
        assert rows(c, "SELECT count(*) FROM transactions") == [(1,)]


def test_connect_closes_connection_on_schema_error(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "SCHEMA", "THIS IS NOT SQL")
    with pytest.raises(sqlite3.Error):
        db.connect(str(tmp_path / "bad.db"))


def test_connect_fails_for_unwritable_path(tmp_path):
    with pytest.raises(sqlite3.OperationalError):
        db.connect(str(tmp_path / "missing-dir" / "t.db"))


def test_transaction_mapping_and_empty_fields(conn):
    db.save_transaction(conn, tx(), "<abc@mail.example.com>")
    assert rows(conn, "SELECT source_email_id, original_merchant, original_amount, account,"
                      " transaction_timestamp, category, transaction_type FROM transactions") == [
        ("<abc@mail.example.com>", "Trader Joe's", "-23.45", "Chase 1234",
         "2026-10-29T22:01:51+00:00", None, None)]
    assert rows(conn, "SELECT count(*) FROM transaction_tags") == [(0,)]


def test_amount_precision_preserved(conn):
    db.save_transaction(conn, tx(amount="0.10"), "<a@x>")
    assert rows(conn, "SELECT original_amount FROM transactions") == [("0.10",)]


def test_same_email_saved_again_keeps_first_values(conn):
    db.save_transaction(conn, tx(merchant="First"), "<a@x>")
    db.save_transaction(conn, tx(merchant="Second"), "<a@x>")
    assert rows(conn, "SELECT original_merchant FROM transactions") == [("First",)]


def test_identical_details_from_different_emails_both_stored(conn):
    db.save_transaction(conn, tx(), "<a@x>")
    db.save_transaction(conn, tx(), "<b@x>")
    assert rows(conn, "SELECT count(*) FROM transactions") == [(2,)]


def test_missing_source_email_id_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        db.save_transaction(conn, tx(), None)


def test_positions_saved_without_balance(conn):
    summary = PositionSummary("Fidelity 5678", "2026-10-29", Decimal(5000),
                              (pos("VTI"), pos("VXUS")))
    db.save_position_summary(conn, summary)
    assert rows(conn, "SELECT ticker, quantity, price, value, account, account_type,"
                      " snapshot_date FROM investment_positions ORDER BY ticker") == [
        ("VTI", "10.5000", "250.10", "2626.05", "Fidelity 5678", "Brokerage", "2026-10-29"),
        ("VXUS", "10.5000", "250.10", "2626.05", "Fidelity 5678", "Brokerage", "2026-10-29")]
    columns = {r[1] for r in rows(conn, "PRAGMA table_info(investment_positions)")}
    assert "balance" not in columns


def test_resaving_position_replaces_values(conn):
    for price in ("250.10", "260.00"):
        db.save_position_summary(conn, PositionSummary("Fidelity 5678", "2026-10-29",
                                                       Decimal(1), (pos(price=price),)))
    assert rows(conn, "SELECT price FROM investment_positions") == [("260.00",)]


def test_same_ticker_on_another_date_is_separate(conn):
    for date in ("2026-10-29", "2026-10-30"):
        db.save_position_summary(conn, PositionSummary("Fidelity 5678", date,
                                                       Decimal(1), (pos(date=date),)))
    assert rows(conn, "SELECT count(*) FROM investment_positions") == [(2,)]


def test_transaction_type_constraint(conn):
    db.save_transaction(conn, tx(), "<a@x>")
    conn.execute("UPDATE transactions SET transaction_type = 'Income'")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE transactions SET transaction_type = 'Gift'")


def test_tags_multiple_unique_and_cascade(conn):
    db.save_transaction(conn, tx(), "<a@x>")
    tid = rows(conn, "SELECT id FROM transactions")[0][0]
    for tag in ("vacation", "shared"):
        conn.execute("INSERT INTO transaction_tags VALUES (?, ?)", (tid, tag))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO transaction_tags VALUES (?, ?)", (tid, "vacation"))
    assert rows(conn, "SELECT count(*) FROM transaction_tags") == [(2,)]
    conn.execute("DELETE FROM transactions WHERE id = ?", (tid,))
    assert rows(conn, "SELECT count(*) FROM transaction_tags") == [(0,)]


def test_failed_save_rolls_back(tmp_path):
    path = str(tmp_path / "t.db")
    with closing(db.connect(path)) as c:
        with pytest.raises(sqlite3.IntegrityError), c:
            db.save_transaction(c, tx(), "<a@x>")
            db.save_transaction(c, tx(), "<b@x>")
            db.save_transaction(c, tx(), None)
        assert rows(c, "SELECT count(*) FROM transactions") == [(0,)]
