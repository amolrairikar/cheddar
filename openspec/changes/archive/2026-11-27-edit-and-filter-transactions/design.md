## Context

Transactions live in SQLite (`api/db.py`). `category`, `transaction_type`, `deleted_at` and the `transaction_tags` table already exist. `_upgrade()` adds columns missing from older databases. Amounts are stored as decimal strings and timestamps as UTC ISO 8601 strings. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Edits never destroy parsed values and are never overwritten by a refresh.

**Non-Goals:**
- Bulk updates, restoring deleted transactions, pagination, amount range filters, or filtering for uncategorized transactions.

## Decisions

- **Nullable override columns `merchant` and `amount`.** Reads return `COALESCE(override, original)`, and writing NULL reverts. Copying the originals into the new columns on insert was rejected: it needs a backfill and loses the distinction between edited and unedited rows. `save_transaction` stays unchanged, so its `ON CONFLICT DO NOTHING` keeps edits through re-imports.
- **`PATCH /transactions/{id}` rather than a bulk body.** Chosen by the user. The path id is bounded to the SQLite integer range so an oversized value responds 422 instead of overflowing into an unhandled 500.
- **Strict request model.** Unknown fields are rejected (`extra="forbid"`), so protected fields fail loudly instead of being silently ignored. Only fields present in the request are applied, which separates "omitted" from `null`. Column names in the UPDATE come from a fixed allowlist.
- **Amounts are formatted in plain notation** (`format(value, "f")`) so exponent notation is never stored. They are limited to 20 digits, because plain formatting of a huge exponent would exhaust memory.
- **Text that is not valid Unicode** (an unpaired surrogate in JSON) is rejected by request validation. Because FastAPI echoes rejected input, the app's validation error handler falls back to a plain 422 message when the echo cannot be encoded. This also fixes the same 500 on `DELETE /transactions`.
- **Filtering in SQL** with fixed WHERE fragments and bound parameters. Filtering in Python was rejected because it loads every row.
- **A registered `casefold` SQL function** for text matching, because SQLite's `lower()` and `LIKE` only fold ASCII. It must pass NULL through. Merchant substring matching uses `instr`, so `%` and `_` are literal.
- **Date filtering compares the first 10 characters of the stored timestamp**, which is the UTC date because all stored timestamps are UTC.
- **Tag filtering uses an `EXISTS` subquery**, so a transaction matching several tags is listed once.

## Risks / Trade-offs

- [Filters scan the whole table] → Acceptable for a local single-user database; indexes can be added later.
- [Date filters use UTC days, so a late-evening local purchase can fall on the next day] → Documented in the API reference.
- [Tags that differ only by case can both be stored] → Tag filtering ignores case, so both are still found.

## Migration Plan

`connect()` adds the two columns to existing databases on first open. Older code ignores them, so rollback needs no schema change.
