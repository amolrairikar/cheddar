## 1. Pipeline

- [x] 1.1 Add `message_id` to `ParsedEntry` in `api/email_parser/loading/pipeline.py`, set from the loaded email's `message_id` (the IMAP UID when the header is missing); verify with `tests/loading/test_pipeline.py` cases for a normal Message-ID and the UID fallback, and that the existing pipeline tests still pass

## 2. Database module

- [x] 2.1 Create `api/db.py` with `db_path()` (reads `CHEDDAR_DB_PATH`, default `./cheddar.db`), `connect(path)` (enables `PRAGMA foreign_keys = ON`, creates tables if missing) and the schema for `transactions` (including `source_email_id TEXT NOT NULL UNIQUE`), `transaction_tags` and `investment_positions`; verify with `tests/db/test_db.py` cases for default and custom path, first-use table creation, and existing rows surviving a reopen
- [x] 2.2 Add `save_transaction(conn, t, source_email_id)` mapping `merchant`/`amount`/`account`/`timestamp` to `original_merchant`/`original_amount`/`account`/`transaction_timestamp`, storing the source email ID, with Decimal stored as text, empty category and type, and `ON CONFLICT (source_email_id) DO NOTHING`; verify with tests for the mapping, source email ID stored, NULL category/type, no tags, precision (`0.10`), saving from the same email twice leaving one row with the first values and no error, identical details from different emails stored as two rows, and a missing source email ID rejected
- [x] 2.3 Add `save_position_summary(conn, s)` upserting each position on (account, ticker, snapshot_date) and not storing the balance; verify with tests for two positions saved, re-save replacing values, same ticker on another date, and Decimal precision (`10.5000`)
- [x] 2.4 Verify schema constraints in tests: invalid `transaction_type` rejected, `Income` accepted, multiple tags allowed, duplicate tag rejected, and deleting a transaction cascades to its tags

## 3. Refresh endpoint

- [x] 3.1 In `api/main.py`, open the database after `load_and_parse` and save all parsed transactions (passing each entry's `message_id`) and position summaries in a single transaction (commit once, roll back on error, connection always closed) before calling `loader.move`; verify with `tests/api/test_main.py` that a refresh with a transaction and a position summary leaves the expected rows and that the transaction records its email's Message-ID
- [x] 3.2 Map database errors (`sqlite3.Error`, `OSError`) to HTTP 500 without moving any email; verify with API tests where saving fails midway: response is 500, the database has no rows from that refresh, and all emails remain in the pending folder
- [x] 3.3 Add API tests for a refresh containing only failed emails (nothing added to the database, emails moved to the failed folder), for a retry after a database failure (same emails saved and moved), and for a refresh whose move fails with 502 followed by a successful refresh (200, emails moved, exactly one transaction per email)
- [x] 3.4 Add an autouse fixture in `tests/api/test_main.py` setting `CHEDDAR_DB_PATH` to `tmp_path` so no test touches a real database; verify the existing API tests still pass

## 4. Wrap-up

- [x] 4.1 Add `*.db` to `.gitignore` and document `CHEDDAR_DB_PATH` (default `./cheddar.db`) in `README.md`; verify both files contain the entries
- [x] 4.2 Run `uv run ruff check .` and `uv run pytest --cov --cov-report=term-missing`; verify both are clean with 100% coverage
