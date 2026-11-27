## 1. Storage

- [x] 1.1 Add nullable `merchant` and `amount` columns to the schema in `api/db.py` and extend `_upgrade()`; verify with tests that upgrade databases both with and without `deleted_at`, and reopen them
- [x] 1.2 Return effective `merchant` and `amount` from `list_transactions` through a shared row helper; verify with db tests for unedited and edited rows, and that re-saving the same email keeps edits
- [x] 1.3 Add `update_transaction` (active rows only, column allowlist, tag replacement, `None` when not found); verify with db tests for set, revert, tags, empty changes, missing and deleted ids
- [x] 1.4 Add filter arguments to `list_transactions` with the `casefold` SQL function; verify with db tests for each filter, combinations, date boundaries, non-ASCII case, literal `%` and NULL category

## 2. API

- [x] 2.1 Add `merchant` and `amount` to `TransactionItem` and add the strict `TransactionUpdate` model in `api/schemas.py`; verify through the endpoint tests in 2.2
- [x] 2.2 Add `PATCH /transactions/{id}` to `api/routers/transactions.py`; verify with API tests for each field, null handling, protected fields, invalid values and ids (422), 404, 500 with rollback, and no blocking during a refresh
- [x] 2.3 Add the filter query parameters and date order check to `GET /transactions`; verify with API tests for filtering and every 422 case, and update the `list_transactions` failure stub

## 3. Documentation and verification

- [x] 3.1 Update `api/API_REFERENCE.md` (PATCH, filters, new fields, errors, remove "no endpoint sets it" notes); verify it matches the code and `/openapi.json`
- [x] 3.2 Run `pytest --cov` (100% required), `ruff check` and `openspec validate edit-and-filter-transactions`
- [x] 3.3 Run the API against a seeded scratchpad database and verify PATCH and filtered GET requests with `curl`
