## 1. Database layer

- [x] 1.1 In `api/db.py`, add `deleted_at TEXT` to the `transactions` schema and, in `connect()`, add the column to an older table via `PRAGMA table_info` + `ALTER TABLE` when missing; verify with `tests/db/test_db.py` cases for a fresh database having the column, an older database (created with the previous schema and two rows) keeping both rows active after `connect`, and opening an upgraded database again without error
- [x] 1.2 Add `soft_delete_transactions(conn, ids) -> list[int]` that sets `deleted_at` to the current UTC time only for active existing ids and returns the ids actually deleted (de-duplicated, first-seen order); verify with tests for deleting some, missing ids, already-deleted ids keeping their original `deleted_at`, duplicate ids, an empty list, and tags and values left unchanged
- [x] 1.3 Add `list_transactions(conn, deleted: bool)` returning rows ordered by id, with each row's tags, for active or soft-deleted transactions; verify with tests for active-only, deleted-only, tags included, and empty
- [x] 1.4 Verify with a test that `save_transaction` for a soft-deleted transaction's source email adds no row and leaves it deleted

## 2. API

- [x] 2.1 In `api/schemas.py`, add `TransactionItem`, `TransactionListResponse`, `DeleteRequest(ids: list[int])` and `DeleteResponse(deleted, not_found)`
- [x] 2.2 In `api/routers/transactions.py`, add `GET /transactions` (`deleted: bool = False`) using `db.list_transactions`, mapping `sqlite3.Error`/`OSError` to 500 with a "could not ... the database" detail; verify with `tests/api/test_main.py` cases for active list, `?deleted=true`, tags shown, empty database, and 500 on a database failure
- [x] 2.3 In `api/routers/transactions.py`, add `DELETE /transactions` using `db.soft_delete_transactions` in one DB transaction, computing `not_found` as requested ids not deleted, 500 on database errors, no use of `_refresh_lock`; verify with API tests for success, partial `not_found`, already deleted, duplicate ids, empty list, deleted rows kept in `?deleted=true`, 422 for `{"ids": ["a"]}` and `{}`, 500 with nothing changed when the database fails, delete while the refresh lock is held returning 200, and a delete followed by a refresh not re-importing the transaction
- [x] 2.4 Put both transaction endpoints in an `APIRouter` in `api/routers/transactions.py` (with an `api/routers/__init__.py`) and include it from `api/main.py`, leaving `/health` and `/refresh_transactions` in `main.py`; verify the existing API tests pass unchanged

## 3. Wrap-up

- [x] 3.1 Run `uv run ruff check .` and `uv run pytest --cov --cov-report=term-missing`; verify both are clean with 100% coverage
