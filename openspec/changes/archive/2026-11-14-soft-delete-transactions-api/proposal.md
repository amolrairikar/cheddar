## Why

Stored transactions cannot be listed or removed through the API, and ids are not exposed anywhere. A mistaken or unwanted transaction (for example a duplicate alert or a test email) stays in the database forever. Deletion should be reversible, so a restore feature can be added later without losing data.

## What Changes

- Add `GET /transactions`, which lists active (not deleted) transactions with their ids. With `?deleted=true` it lists soft-deleted transactions instead.
- Add `DELETE /transactions` with body `{"ids": [1, 2, 3]}`. It soft-deletes every listed transaction that exists and is active, and responds 200 with `{"deleted": [...], "not_found": [...]}`. Ids that do not exist or are already deleted are reported in `not_found`; they are never an error.
- Add a nullable `deleted_at` column to `transactions` (UTC timestamp, empty means active). A delete sets it; nothing is removed, so tags and the source email ID are kept.
- Existing databases created before this change are upgraded in place on open: the column is added and existing rows stay active.
- A refresh never re-imports a soft-deleted transaction, because its source email ID is still stored.
- Invalid request bodies get 422; database failures get 500 with no partial change.
- Not included: deleting all transactions, restoring (undeleting) transactions, and permanently removing (purging) rows. Restore is future work.

## Capabilities

### New Capabilities
- `transaction-api`: HTTP endpoints to list active or soft-deleted transactions and to soft-delete transactions by id.

### Modified Capabilities
- `persistence`: transactions gain a `deleted_at` marker, existing databases are upgraded in place, and a soft-deleted transaction is not re-imported by a later save of the same source email.

## Impact

- Code: `api/db.py` (schema, in-place upgrade in `connect`, list and soft-delete functions), `api/schemas.py` (list, request and delete response models), `api/main.py` (two endpoints).
- Tests: `tests/db/test_db.py` and `tests/api/test_main.py`. Coverage must stay at 100%.
- Specs: new `transaction-api` spec and a delta for `persistence`.
- No new dependencies. `POST /refresh_transactions` is unchanged.
