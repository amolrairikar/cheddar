## Context

`POST /refresh_transactions` (`api/main.py`) runs `load_and_parse`, then moves parsed and failed emails, all inside `_refresh_lock` and one `ImapLoader` session. Results are `Transaction` and `PositionSummary` dataclasses (`api/email_parser/parsing/models.py`). Amounts and quantities are `Decimal`. The project has no database layer. See proposal.md for motivation.

Constraints: stdlib `sqlite3` only; pytest runs with `filterwarnings = error`, so an unclosed connection fails tests; coverage must stay at 100%.

## Goals / Non-Goals

**Goals:**
- Durable storage of transactions and positions with the field mapping in the specs.
- Persist-before-move ordering, with all-or-nothing writes per refresh.

**Non-Goals:**
- Endpoints to read, categorize or tag data.
- Schema migrations (tables are created if missing; no versioning yet).
- Storing the position summary's balance.
- Detecting duplicates by content (merchant, amount, timestamp); only the source email identifies a duplicate.

## Decisions

**1. A small `api/db.py` module on stdlib `sqlite3`.**
It exposes `connect(path)`, `init_schema(conn)`, `save_transaction(conn, t)` and `save_position_summary(conn, s)`, plus a helper to read `CHEDDAR_DB_PATH`. Alternative: SQLAlchemy. Rejected as a heavy dependency for three tables, and it would change `uv.lock`.

**2. Schema.**
`transactions` has `id INTEGER PRIMARY KEY`, `original_merchant`, `original_amount`, `account`, `transaction_timestamp`, nullable `category`, and nullable `transaction_type` with `CHECK (transaction_type IN ('Income','Expense'))`. `transaction_tags(transaction_id REFERENCES transactions(id) ON DELETE CASCADE, tag, PRIMARY KEY (transaction_id, tag))`. `investment_positions` holds the `PositionOut` fields with `PRIMARY KEY (account, ticker, snapshot_date)`.
Tags live in their own table rather than a JSON or comma-separated column: it allows filtering by tag with a plain join, single-row add and remove, enforced uniqueness, and cascade deletion. Cost: one extra table and a join on read.

**3. `Decimal` stored as TEXT.**
SQLite has no exact decimal type, and REAL would round. `str(Decimal)` round-trips exactly (`0.10` stays `0.10`). Alternative: integer cents. Rejected because quantities and prices have varying scale. Trade-off: numeric ordering and sums in SQL need a cast; acceptable for now.

**4. Foreign keys on every connection.**
SQLite ignores `REFERENCES` unless `PRAGMA foreign_keys = ON` is set per connection, so `connect` sets it. Without it, tag cascade would silently not work.

**5. One DB transaction per refresh, committed once.**
The endpoint opens a connection, saves everything, then commits; any exception rolls back. Use `contextlib.closing` for the connection and the `with conn:` commit/rollback behavior of `sqlite3`, so the connection is always closed (needed for `filterwarnings = error`).
Positions use `INSERT ... ON CONFLICT (account, ticker, snapshot_date) DO UPDATE`, so a re-sent snapshot overwrites instead of failing the whole refresh.

**6. Refresh order: load -> parse -> persist -> move.**
Persist inside the existing `with ImapLoader(...)` block, after `load_and_parse` and before `loader.move`. `sqlite3.Error` (and `OSError` when the file or directory is unusable) maps to HTTP 500 with a generic message that does not echo credentials. Because the commit happens before any move, a DB failure leaves every email pending for the next refresh. Alternative: move first, then persist. Rejected, since a persistence failure would lose emails from the queue.

**7. Dedupe transactions by source email Message-ID.**
`transactions` gets `source_email_id TEXT NOT NULL UNIQUE`, filled from `Email.message_id` (which already falls back to the IMAP UID when the header is missing). `save_transaction` uses `INSERT ... ON CONFLICT (source_email_id) DO NOTHING`, so a repeated email is silently skipped instead of failing the whole refresh. This closes the case where data is committed but the IMAP move then fails: the next refresh re-reads the same emails and stores nothing new. Alternative: a natural-key unique constraint on (account, timestamp, merchant, amount). Rejected because two genuine identical purchases in the same second would collapse. Alternative: `ON CONFLICT REPLACE`. Rejected so that later edits to category, type and tags are never overwritten by a re-read.

**8. `ParsedEntry` carries the email's Message-ID.**
`ParsedEntry` (in `api/email_parser/loading/pipeline.py`) gains a `message_id` field set from the loaded email, so `main.py` can pass it to `save_transaction`. This is an internal change to the loading layer: `uid` and `result` are unchanged, nothing else constructs `ParsedEntry` outside the pipeline and its tests, and the public response is not affected. Position summaries ignore it.

**9. Tests use a temporary database.**
An autouse fixture in `tests/api/test_main.py` sets `CHEDDAR_DB_PATH` to `tmp_path`, so tests never touch a real file. `tests/db/test_db.py` uses an in-memory or `tmp_path` database. Needs `tests/db` on the pytest path only if imports require it; `api` is already on `pythonpath`.

## Risks / Trade-offs

- [A failure after commit but before/while moving emails (e.g. IMAP error -> 502) leaves saved data with emails still pending] -> The next refresh skips already-stored transactions via the unique source email ID, and positions upsert, so nothing is duplicated.
- [An email without a Message-ID falls back to its IMAP UID, and UIDs can be reused after the folder's UIDVALIDITY changes or across the pending folder's lifetime, so a new email could be mistaken for an old one and skipped] -> Rare, since real bank emails carry a Message-ID; accepted.
- [A bank resending a notification with the same Message-ID is ignored] -> Intended; that is the same email.
- [Existing databases lack the new column] -> Not applicable yet, as no database has been created by a released version; tables are created fresh.
- [Concurrent refreshes] -> The existing `_refresh_lock` already serializes them; no extra locking needed.
- [DB file path unwritable] -> Surfaces as HTTP 500 before any email is moved.
- [TEXT decimals] -> Numeric SQL needs casts; revisit when reporting queries are built.
- [No schema versioning] -> `CREATE TABLE IF NOT EXISTS` cannot alter existing tables; a migration step will be needed when the schema changes.
