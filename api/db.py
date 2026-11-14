"""SQLite storage for parsed transactions and investment positions."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime

from email_parser.parsing.models import PositionSummary, Transaction

DEFAULT_DB_PATH = "./cheddar.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    source_email_id TEXT NOT NULL UNIQUE,
    original_merchant TEXT NOT NULL,
    original_amount TEXT NOT NULL,
    account TEXT NOT NULL,
    transaction_timestamp TEXT NOT NULL,
    category TEXT,
    transaction_type TEXT CHECK (transaction_type IN ('Income', 'Expense')),
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS transaction_tags (
    transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (transaction_id, tag)
);

CREATE TABLE IF NOT EXISTS investment_positions (
    ticker TEXT NOT NULL,
    quantity TEXT NOT NULL,
    price TEXT NOT NULL,
    value TEXT NOT NULL,
    account TEXT NOT NULL,
    account_type TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    PRIMARY KEY (account, ticker, snapshot_date)
);
"""


def db_path(env: Mapping[str, str] | None = None) -> str:
    """The database file named by ``CHEDDAR_DB_PATH`` (default ``./cheddar.db``)."""
    env = os.environ if env is None else env
    return env.get("CHEDDAR_DB_PATH") or DEFAULT_DB_PATH


def connect(path: str) -> sqlite3.Connection:
    """Open the database, enable foreign keys and create missing tables.

    The caller must close the connection (e.g. with ``contextlib.closing``).
    """
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        _upgrade(conn)
    except BaseException:
        conn.close()
        raise
    return conn


def _upgrade(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a database was first created."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(transactions)")}
    if "deleted_at" not in columns:
        conn.execute("ALTER TABLE transactions ADD COLUMN deleted_at TEXT")


def save_transaction(conn: sqlite3.Connection, t: Transaction, source_email_id: str) -> None:
    """Store a transaction; one already stored for the same email is left unchanged."""
    conn.execute(
        "INSERT INTO transactions (source_email_id, original_merchant, original_amount,"
        " account, transaction_timestamp) VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT (source_email_id) DO NOTHING",
        (source_email_id, t.merchant, str(t.amount), t.account, t.timestamp),
    )


def save_position_summary(conn: sqlite3.Connection, s: PositionSummary) -> None:
    """Store each position, replacing one with the same account, ticker and date."""
    conn.executemany(
        "INSERT INTO investment_positions (ticker, quantity, price, value, account,"
        " account_type, snapshot_date) VALUES (?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT (account, ticker, snapshot_date) DO UPDATE SET"
        " quantity = excluded.quantity, price = excluded.price, value = excluded.value,"
        " account_type = excluded.account_type",
        [(p.ticker, str(p.quantity), str(p.price), str(p.value), p.account,
          p.account_type, p.snapshot_date) for p in s.positions],
    )


def soft_delete_transactions(conn: sqlite3.Connection, ids: list[int]) -> list[int]:
    """Mark active transactions deleted; return the ids actually deleted.

    Missing and already deleted ids are skipped. Duplicates are handled once.
    """
    now = datetime.now(UTC).isoformat()
    deleted = []
    for transaction_id in dict.fromkeys(ids):
        cursor = conn.execute(
            "UPDATE transactions SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
            (now, transaction_id),
        )
        if cursor.rowcount:
            deleted.append(transaction_id)
    return deleted


def list_transactions(conn: sqlite3.Connection, deleted: bool) -> list[dict]:
    """Active (or, with ``deleted``, soft-deleted) transactions ordered by id, with tags."""
    condition = "IS NOT NULL" if deleted else "IS NULL"
    rows = conn.execute(
        "SELECT id, original_merchant, original_amount, account, transaction_timestamp,"
        " category, transaction_type, deleted_at FROM transactions"
        f" WHERE deleted_at {condition} ORDER BY id"
    ).fetchall()
    tags: dict[int, list[str]] = {}
    for transaction_id, tag in conn.execute(
        "SELECT transaction_id, tag FROM transaction_tags ORDER BY tag"
    ):
        tags.setdefault(transaction_id, []).append(tag)
    keys = ("id", "original_merchant", "original_amount", "account",
            "transaction_timestamp", "category", "transaction_type", "deleted_at")
    return [dict(zip(keys, row), tags=tags.get(row[0], [])) for row in rows]
