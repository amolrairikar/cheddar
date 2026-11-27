## Why

Stored transactions have a category, transaction type and tags, but no endpoint can set them, and parsed merchant names and amounts cannot be corrected. `GET /transactions` can only filter by deletion state, so a client has to download everything to find the transactions it needs.

## What Changes

- Add `PATCH /transactions/{id}`, which edits one active transaction's `merchant`, `amount`, `category`, `transaction_type` and `tags`.
- `id`, `original_merchant`, `original_amount`, `transaction_timestamp`, `account` and `deleted_at` cannot be modified.
- Editing `merchant` or `amount` stores an override. The parsed original values are kept, and clearing an edit reverts to them.
- `GET /transactions` items gain `merchant` and `amount` (the edited value, otherwise the original).
- `GET /transactions` gains filters: `start_date`, `end_date`, `merchant`, `category`, `account`, `tag` and `transaction_type`. Invalid filter values respond 422.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `transaction-api`: new update endpoint and list filters; list items gain `merchant` and `amount`; errors cover the new endpoint and parameters.
- `persistence`: transactions can hold edited merchant and amount values beside the originals; existing databases are upgraded in place.

## Impact

- Code: `api/db.py`, `api/schemas.py`, `api/routers/transactions.py`.
- Docs: `api/API_REFERENCE.md`.
- Data: two new nullable columns on the `transactions` table, added automatically to existing databases.
- API: additive and backward compatible. No new dependencies.
