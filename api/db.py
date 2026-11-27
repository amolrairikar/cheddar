"""SQLite storage for parsed transactions and investment positions."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime

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
    deleted_at TEXT,
    merchant TEXT,
    amount TEXT
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


# Transaction columns a client may edit. merchant and amount override the originals.
EDITABLE_COLUMNS = frozenset({"merchant", "amount", "category", "transaction_type"})

# The merchant and amount a client sees: the edit if there is one, else the original.
_MERCHANT = "COALESCE(merchant, original_merchant)"
_AMOUNT = "COALESCE(amount, original_amount)"


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
        # SQLite's own lower() and LIKE only ignore case for ASCII.
        conn.create_function("casefold", 1, _casefold, deterministic=True)
        conn.executescript(SCHEMA)
        _upgrade(conn)
    except BaseException:
        conn.close()
        raise
    return conn


def _casefold(value: str | None) -> str | None:
    return None if value is None else value.casefold()


def _upgrade(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a database was first created."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(transactions)")}
    for column in ("deleted_at", "merchant", "amount"):
        if column not in columns:
            conn.execute(f"ALTER TABLE transactions ADD COLUMN {column} TEXT")


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


def update_transaction(
    conn: sqlite3.Connection, transaction_id: int, changes: Mapping[str, object]
) -> dict | None:
    """Apply ``changes`` to an active transaction and return it, or None if there is none.

    Keys are ``EDITABLE_COLUMNS`` and ``tags``. A None column value clears it, and
    ``tags`` replaces all of the transaction's tags. Absent keys are left unchanged.
    """
    columns = {name: value for name, value in changes.items() if name != "tags"}
    if unknown := columns.keys() - EDITABLE_COLUMNS:
        raise ValueError(f"columns cannot be edited: {', '.join(sorted(unknown))}")
    # With no column changes, a no-op assignment still tells whether the row is active.
    assignments = ", ".join(f"{name} = ?" for name in columns) or "id = id"
    cursor = conn.execute(
        f"UPDATE transactions SET {assignments} WHERE id = ? AND deleted_at IS NULL",
        (*columns.values(), transaction_id),
    )
    if not cursor.rowcount:
        return None
    if "tags" in changes:
        conn.execute("DELETE FROM transaction_tags WHERE transaction_id = ?", (transaction_id,))
        conn.executemany(
            "INSERT INTO transaction_tags (transaction_id, tag) VALUES (?, ?)",
            [(transaction_id, tag) for tag in dict.fromkeys(changes["tags"])],
        )
    [item] = _select_transactions(conn, ["id = ?"], [transaction_id])
    return item


def list_transactions(
    conn: sqlite3.Connection,
    deleted: bool,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    merchants: Sequence[str] | None = None,
    categories: Sequence[str] | None = None,
    accounts: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
    transaction_types: Sequence[str] | None = None,
) -> list[dict]:
    """Active (or, with ``deleted``, soft-deleted) transactions ordered by id, with tags.

    A transaction must satisfy every filter given, and satisfies a list filter
    when it matches any of its values. Text matching ignores case. ``merchants``
    match part of the merchant; the other text filters match the whole value.
    Dates are inclusive UTC days.
    """
    conditions = ["deleted_at IS NOT NULL" if deleted else "deleted_at IS NULL"]
    params: list[str] = []

    def any_of(condition: str, values: Sequence[str] | None) -> None:
        if values:
            conditions.append(f"({' OR '.join([condition] * len(values))})")
            params.extend(values)

    # Stored timestamps are UTC ISO 8601, so the first 10 characters are the UTC date.
    for operator, day in ((">=", start_date), ("<=", end_date)):
        if day is not None:
            conditions.append(f"substr(transaction_timestamp, 1, 10) {operator} ?")
            params.append(day.isoformat())
    # instr rather than LIKE, so that % and _ are matched literally.
    any_of(f"instr(casefold({_MERCHANT}), casefold(?)) > 0", merchants)
    any_of("casefold(category) = casefold(?)", categories)
    any_of("casefold(account) = casefold(?)", accounts)
    any_of("EXISTS (SELECT 1 FROM transaction_tags WHERE transaction_id = transactions.id"
           " AND casefold(tag) = casefold(?))", tags)
    any_of("transaction_type = ?", transaction_types)
    return _select_transactions(conn, conditions, params)


def _select_transactions(
    conn: sqlite3.Connection, conditions: list[str], params: Sequence[object]
) -> list[dict]:
    """Transactions meeting all ``conditions`` (SQL fragments, never client text)."""
    rows = conn.execute(
        f"SELECT id, original_merchant, original_amount, {_MERCHANT}, {_AMOUNT}, account,"
        " transaction_timestamp, category, transaction_type, deleted_at FROM transactions"
        f" WHERE {' AND '.join(conditions)} ORDER BY id",
        params,
    ).fetchall()
    tags: dict[int, list[str]] = {}
    for transaction_id, tag in conn.execute(
        "SELECT transaction_id, tag FROM transaction_tags ORDER BY tag"
    ):
        tags.setdefault(transaction_id, []).append(tag)
    keys = ("id", "original_merchant", "original_amount", "merchant", "amount", "account",
            "transaction_timestamp", "category", "transaction_type", "deleted_at")
    return [dict(zip(keys, row), tags=tags.get(row[0], [])) for row in rows]
