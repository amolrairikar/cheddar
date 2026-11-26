## Why

`POST /refresh_transactions` processes the whole pending email folder, saving investment positions as well as transactions. The name suggests it only handles transactions.

## What Changes

- **BREAKING**: Rename `POST /refresh_transactions` to `POST /refresh`. The old path is removed, with no alias or redirect.
- Behavior, response body and error responses are unchanged. No per-type counts are added.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `refresh-api`: the refresh endpoint's path changes to `POST /refresh`.

## Impact

- `api/main.py`: route and handler name.
- `tests/api/test_main.py`: requested paths.
- `openspec/specs/refresh-api/spec.md`: updated on sync, including the Purpose wording "transaction refresh".
- Any client or scheduler calling the old path must be updated. No caller exists in this repository outside the tests, and the old path is assumed to need no transition period.
