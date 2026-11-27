import sqlite3
from contextlib import closing
from datetime import date as Date
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


OLD_SCHEMA = """
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY,
    source_email_id TEXT NOT NULL UNIQUE,
    original_merchant TEXT NOT NULL,
    original_amount TEXT NOT NULL,
    account TEXT NOT NULL,
    transaction_timestamp TEXT NOT NULL,
    category TEXT,
    transaction_type TEXT CHECK (transaction_type IN ('Income', 'Expense'))
);
"""


def seed(conn, count=3):
    for n in range(count):
        db.save_transaction(conn, tx(merchant=f"M{n}"), f"<{n}@x>")


def test_fresh_database_has_deleted_at_column(conn):
    columns = [r[1] for r in rows(conn, "PRAGMA table_info(transactions)")]
    assert "deleted_at" in columns


def test_older_database_is_upgraded_in_place(tmp_path):
    path = str(tmp_path / "old.db")
    with closing(sqlite3.connect(path)) as old, old:
        old.executescript(OLD_SCHEMA)
        old.executemany(
            "INSERT INTO transactions (source_email_id, original_merchant, original_amount,"
            " account, transaction_timestamp) VALUES (?, 'M', '1.00', 'A', 'T')",
            [("<1@x>",), ("<2@x>",)],
        )
    with closing(db.connect(path)) as c:
        assert rows(c, "SELECT source_email_id, deleted_at FROM transactions ORDER BY id") == [
            ("<1@x>", None), ("<2@x>", None)]
    with closing(db.connect(path)) as c:
        assert rows(c, "SELECT count(*) FROM transactions") == [(2,)]


def test_new_transaction_is_active(conn):
    seed(conn, 1)
    assert rows(conn, "SELECT deleted_at FROM transactions") == [(None,)]


def test_soft_delete_some_and_missing(conn):
    seed(conn)
    assert db.soft_delete_transactions(conn, [1, 3, 99]) == [1, 3]
    assert rows(conn, "SELECT id FROM transactions WHERE deleted_at IS NOT NULL ORDER BY id") == [
        (1,), (3,)]


def test_soft_delete_keeps_values_and_tags(conn):
    seed(conn, 1)
    conn.execute("INSERT INTO transaction_tags VALUES (1, 'vacation')")
    db.soft_delete_transactions(conn, [1])
    assert rows(conn, "SELECT original_merchant, source_email_id FROM transactions") == [
        ("M0", "<0@x>")]
    assert rows(conn, "SELECT tag FROM transaction_tags") == [("vacation",)]


def test_soft_delete_twice_keeps_first_time(conn):
    seed(conn, 1)
    assert db.soft_delete_transactions(conn, [1]) == [1]
    first = rows(conn, "SELECT deleted_at FROM transactions")
    assert db.soft_delete_transactions(conn, [1]) == []
    assert rows(conn, "SELECT deleted_at FROM transactions") == first


def test_soft_delete_duplicate_ids_and_empty(conn):
    seed(conn, 1)
    assert db.soft_delete_transactions(conn, [1, 1]) == [1]
    assert db.soft_delete_transactions(conn, []) == []


def test_list_active_and_deleted(conn):
    seed(conn)
    db.soft_delete_transactions(conn, [2])
    assert [t["id"] for t in db.list_transactions(conn, deleted=False)] == [1, 3]
    listed = db.list_transactions(conn, deleted=True)
    assert [t["id"] for t in listed] == [2]
    assert listed[0]["deleted_at"] is not None
    assert listed[0]["original_merchant"] == "M1"


def test_list_includes_tags(conn):
    seed(conn, 2)
    conn.executemany("INSERT INTO transaction_tags VALUES (?, ?)",
                     [(1, "vacation"), (1, "shared")])
    listed = db.list_transactions(conn, deleted=False)
    assert listed[0]["tags"] == ["shared", "vacation"]
    assert listed[1]["tags"] == []


def test_list_empty(conn):
    assert db.list_transactions(conn, deleted=False) == []


def test_soft_deleted_transaction_is_not_reimported(conn):
    seed(conn, 1)
    db.soft_delete_transactions(conn, [1])
    db.save_transaction(conn, tx(merchant="Other"), "<0@x>")
    assert rows(conn, "SELECT original_merchant, deleted_at IS NOT NULL FROM transactions") == [
        ("M0", 1)]


def test_database_without_edit_columns_is_upgraded(tmp_path):
    path = str(tmp_path / "old.db")
    with closing(sqlite3.connect(path)) as old, old:
        old.executescript(OLD_SCHEMA)
        old.execute("ALTER TABLE transactions ADD COLUMN deleted_at TEXT")
        old.execute(
            "INSERT INTO transactions (source_email_id, original_merchant, original_amount,"
            " account, transaction_timestamp, deleted_at) VALUES ('<1@x>', 'M', '1.00', 'A',"
            " 'T', 'D')")
    for _ in range(2):
        with closing(db.connect(path)) as c:
            assert rows(c, "SELECT original_merchant, deleted_at, merchant, amount"
                           " FROM transactions") == [("M", "D", None, None)]


def ids(conn, **filters):
    return [t["id"] for t in db.list_transactions(conn, False, **filters)]


def test_update_set_and_revert(conn):
    seed(conn, 1)
    item = db.update_transaction(conn, 1, {"merchant": "New", "amount": "0.10"})
    assert (item["merchant"], item["amount"]) == ("New", "0.10")
    assert (item["original_merchant"], item["original_amount"]) == ("M0", "-23.45")
    item = db.update_transaction(conn, 1, {"merchant": None, "amount": None})
    assert (item["merchant"], item["amount"]) == ("M0", "-23.45")


def test_update_tags_only_touches_that_transaction(conn):
    seed(conn, 2)
    db.update_transaction(conn, 2, {"tags": ["keep"]})
    assert db.update_transaction(conn, 1, {"tags": ["b", "a", "b"]})["tags"] == ["a", "b"]
    assert db.update_transaction(conn, 1, {})["tags"] == ["a", "b"]
    assert db.update_transaction(conn, 1, {"tags": []})["tags"] == []
    assert rows(conn, "SELECT * FROM transaction_tags") == [(2, "keep")]


def test_update_missing_or_deleted_returns_none(conn):
    seed(conn, 1)
    assert db.update_transaction(conn, 9, {"tags": ["a"]}) is None
    db.soft_delete_transactions(conn, [1])
    assert db.update_transaction(conn, 1, {"category": "X", "tags": ["a"]}) is None
    assert rows(conn, "SELECT category FROM transactions") == [(None,)]
    assert rows(conn, "SELECT count(*) FROM transaction_tags") == [(0,)]


def test_update_rejects_protected_columns(conn):
    seed(conn, 1)
    with pytest.raises(ValueError, match="account"):
        db.update_transaction(conn, 1, {"account": "Other"})


def test_resaving_same_email_keeps_edits(conn):
    seed(conn, 1)
    edited = db.update_transaction(
        conn, 1, {"merchant": "New", "amount": "1", "category": "C",
                  "transaction_type": "Income", "tags": ["t"]})
    db.save_transaction(conn, tx(merchant="Reimported"), "<0@x>")
    assert db.list_transactions(conn, deleted=False) == [edited]


def test_filter_dates_are_inclusive_utc_days(conn):
    stamps = ["2026-09-30T23:59:59+00:00", "2026-10-01T00:00:00+00:00",
              "2026-10-31T23:59:59+00:00", "2026-11-01T00:00:00+00:00"]
    for n, stamp in enumerate(stamps):
        db.save_transaction(conn, tx(timestamp=stamp), f"<{n}@x>")
    assert ids(conn, start_date=Date(2026, 10, 1), end_date=Date(2026, 10, 31)) == [2, 3]
    assert ids(conn, start_date=Date(2026, 10, 31)) == [3, 4]
    assert ids(conn, end_date=Date(2026, 10, 1)) == [1, 2]


def test_filter_text_ignores_case_beyond_ascii_and_is_literal(conn):
    db.save_transaction(conn, tx(merchant="CAFÉ 100%_OFF", account="Épargne"), "<a@x>")
    db.save_transaction(conn, tx(merchant="Cafe 100 XOFF"), "<b@x>")
    db.update_transaction(conn, 1, {"category": "Straße", "tags": ["Été"]})
    assert ids(conn, merchants=["café"]) == [1]
    assert ids(conn, merchants=["%_"]) == [1]
    assert ids(conn, accounts=["épargne"]) == [1]
    assert ids(conn, categories=["STRASSE"]) == [1]  # NULL category never matches
    assert ids(conn, tags=["été"]) == [1]
    assert ids(conn, merchants=["' OR 1=1 --"]) == []


def test_filters_combine(conn):
    seed(conn)
    db.update_transaction(conn, 1, {"transaction_type": "Expense", "tags": ["a", "b"]})
    db.update_transaction(conn, 2, {"transaction_type": "Income", "tags": ["b"]})
    assert ids(conn, tags=["a", "b"]) == [1, 2]
    assert ids(conn, tags=["b"], transaction_types=["Income"]) == [2]
    assert ids(conn, merchants=["m0", "m1"], transaction_types=["Expense"]) == [1]
    assert ids(conn, tags=[]) == [1, 2, 3]
