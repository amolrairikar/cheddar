## Why

`POST /refresh_transactions` parses emails and returns the results, but nothing is stored, and the emails are then moved out of the pending folder. Without persistence the parsed data is lost as soon as the response is read. Storing transactions and investment positions in SQLite gives the planned application a durable source of data to categorize, tag and report on.

## What Changes

- Add a SQLite database (stdlib `sqlite3`, no new dependencies) at the path in `CHEDDAR_DB_PATH`, default `./cheddar.db`. Tables are created automatically if missing. `*.db` is added to `.gitignore`.
- Persist each parsed transaction to a `transactions` table: `merchant` -> `original_merchant`, `amount` -> `original_amount`, `account` -> `account`, `timestamp` -> `transaction_timestamp`. The `category` and `transaction_type` (`Income` or `Expense`) columns are left empty for later.
- Add a `transaction_tags` table so a transaction can carry any number of tags. New transactions have none.
- Persist each position from a parsed position summary to an `investment_positions` table, with the `PositionOut` fields as-is. A position is identified by (account, ticker, snapshot date), and re-saving the same one overwrites it. The account balance on the summary is not stored.
- Change the refresh order to load -> parse -> persist -> move. Emails are moved only after the data is committed. Persistence is all-or-nothing per refresh.
- A database failure makes the refresh respond 500, leaves nothing partially stored, and leaves the emails in the pending folder so a later refresh can retry.
- Each transaction records the Message-ID of the email it came from (`source_email_id`, required and unique). Saving a transaction from an email that is already stored is ignored, so re-processing an email can never create a duplicate. Handled emails also leave the pending folder (previous change `move-processed-emails`), but the database no longer depends on that alone.
- The load/parse pipeline exposes each parsed email's Message-ID alongside its UID so the endpoint can record it. Investment positions are unchanged (they already overwrite on re-save).

## Capabilities

### New Capabilities
- `persistence`: SQLite storage of parsed transactions (with tags) and investment positions, including database location, schema, field mapping and atomic writes.

### Modified Capabilities
- `refresh-api`: a refresh persists parsed results before moving emails, and database failures produce HTTP 500 without moving any email.

## Impact

- Code: new `api/db.py`; `api/main.py` (persist between parse and move); `api/email_parser/loading/pipeline.py` (`ParsedEntry` carries the email's Message-ID); `.gitignore`.
- Tests: new `tests/db/test_db.py`; `tests/loading/test_pipeline.py` (Message-ID on parsed entries); `tests/api/test_main.py` points the database at a temporary path for every test. Coverage must stay at 100%.
- Docs: `README.md` documents `CHEDDAR_DB_PATH`.
- Specs: new `persistence` spec and a delta for `refresh-api`.
- No new dependencies and no change to the response body.
