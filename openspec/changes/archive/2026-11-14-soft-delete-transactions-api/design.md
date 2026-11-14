## Context

`api/main.py` is a single FastAPI module with plain sync handlers. `api/db.py` opens a new stdlib `sqlite3` connection per operation (`with closing(db.connect(db.db_path())) as conn, conn:`) and creates tables with `CREATE TABLE IF NOT EXISTS`. `transactions.id` is an auto-assigned integer; `source_email_id` is unique and `save_transaction` uses `ON CONFLICT (source_email_id) DO NOTHING`. No endpoint exposes ids today. See proposal.md for motivation.

Constraints: stdlib only; pytest runs with `filterwarnings = error` (unclosed connections fail tests); coverage must stay at 100%.

## Goals / Non-Goals

**Goals:**
- Reversible deletion by id, with ids discoverable through the API.
- Existing databases keep working with no manual step.

**Non-Goals:**
- Restore, purge and delete-all endpoints (restore is future work; the data model must make it a one-column update).
- Filtering, paging or searching the list.
- Authentication.

## Decisions

**1. A nullable `deleted_at TEXT` column, not a separate trash table or a boolean.**
NULL means active; otherwise a UTC ISO-8601 timestamp (`datetime.now(timezone.utc).isoformat()`). The timestamp costs nothing over a boolean and records when it happened, which a later purge-after-N-days feature can use. A trash table would need copying rows and tags both ways and would break the foreign key from `transaction_tags`. Because the row never moves, tags are retained with no extra work (the `ON DELETE CASCADE` only fires on a real delete, which this feature never does).

**2. Soft-deleted rows still block re-import.**
`source_email_id` stays stored, so `ON CONFLICT DO NOTHING` already makes a later refresh skip the email. No change to `save_transaction`; a test pins this behavior. Trade-off: a user cannot re-import a deleted transaction by reprocessing its email; restore (future) is the way back.

**3. In-place upgrade inside `connect()`.**
`CREATE TABLE IF NOT EXISTS` leaves an older `transactions` table untouched, so after the schema script `connect` reads `PRAGMA table_info(transactions)` and, if `deleted_at` is missing, runs `ALTER TABLE transactions ADD COLUMN deleted_at TEXT`. It is idempotent, cheap, and existing rows get NULL (active). Alternative: a versioned migration framework (`PRAGMA user_version`). Rejected as overkill for one column; revisit if a second migration appears. The new schema text includes the column so fresh databases need no ALTER.

**4. Soft delete is one conditional UPDATE.**
`UPDATE transactions SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL`, per distinct id, collecting ids whose `rowcount` is 1 into `deleted`; the rest of the requested ids go to `not_found`. This makes "already deleted" and "missing" the same outcome without a prior SELECT, and keeps the original deletion time on repeats. All ids are processed in one DB transaction so a failure changes nothing. Request ids are de-duplicated preserving first-seen order, and the response lists keep that order.

**5. Routes and shapes.**
`GET /transactions?deleted=false` (bool query param) and `DELETE /transactions` with a JSON body model `{ids: list[int]}`. A body on DELETE is unusual but supported by FastAPI and `TestClient.request("DELETE", ..., json=...)`; chosen over `POST /transactions/delete` to keep the resource semantics the user asked for. Responses are pydantic models in `api/schemas.py` (`TransactionItem`, `TransactionListResponse`, `DeleteRequest`, `DeleteResponse`). Amounts stay strings, as stored. Tags are loaded with a single query for the returned ids and grouped in Python, avoiding per-row queries.

**6. Errors.**
Validation failures come from FastAPI as 422. `sqlite3.Error`/`OSError` map to 500 with a short "could not ... the database" detail, same as `_persist`.

**7. No refresh lock.**
Delete writes only `deleted_at` on rows that already exist; refresh only inserts new rows and moves mail. SQLite serializes writers, and a busy database surfaces as `sqlite3.OperationalError`, which is the 500 path. So delete neither takes nor checks `_refresh_lock`.

**8. Transaction endpoints in their own router module.**
`GET /transactions` and `DELETE /transactions` live in `api/routers/transactions.py` as an `APIRouter` that `api/main.py` includes, so `main.py` does not grow with every new resource. `/health` and `/refresh_transactions` stay in `main.py` because the refresh endpoint shares `_refresh_lock` and `_persist` with nothing else; moving it is a separate decision. URLs, request and response shapes and error behavior are unchanged, so no spec changes. Alternative: keep everything in `main.py`. Rejected for scalability.

## Risks / Trade-offs

- [Concurrent writer holds the SQLite lock, delete fails with "database is locked"] -> returns 500 and changes nothing; the client can retry. Not worth a custom busy timeout now.
- [Soft-deleted data accumulates forever] -> acceptable at personal-finance volumes; a purge endpoint is a possible follow-up.
- [DELETE with a request body is dropped by some proxies/clients] -> this API is called directly or by a scheduler; revisit if a client cannot send it.
- [`ALTER TABLE` on every connect adds a `PRAGMA` call] -> negligible for SQLite.

## Migration Plan

No manual step. The first `connect()` against an older `cheddar.db` adds the column. Rollback: older code ignores the extra column, so reverting the code is safe; the column can stay.
