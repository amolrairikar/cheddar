## Why

Every `POST /refresh_transactions` re-reads every email in the pending folder, because the loader never changes the mailbox. That makes repeated refreshes redo work and, once parsed data is persisted (a follow-up change), would insert the same transactions again. Moving each email out of the pending folder once it has been handled makes the pending folder a work queue and gives us dedupe without any database-level logic.

## What Changes

- After a refresh, each email that parsed successfully is moved from the pending folder (`CHEDDAR_IMAP_FOLDER`, default `transactions-pending`) to a processed folder (`CHEDDAR_IMAP_PROCESSED_FOLDER`, default `transactions-processed`).
- Each email that failed (could not be fetched/decoded, no parser recognizes it, or a parser raised a parse error) is moved to a failed folder (`CHEDDAR_IMAP_FAILED_FOLDER`, default `transactions-failed`).
- `ImapLoader` gains a separate move step (e.g. `move(uids, folder)`) that the API calls after `load_and_parse`. Moving is **not** done inside `load_and_parse`, so the follow-up `sqlite-persistence` change can order it as parse -> persist -> move.
- **BREAKING**: the loader and refresh endpoint no longer leave the mailbox unchanged. The "read-only mailbox access" and "mailbox is not modified" requirements are replaced.
- Destination folders must already exist; if a move fails, the refresh responds 502.
- Out of scope: persisting data to SQLite (separate change `sqlite-persistence`).

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `email-loader`: new env settings for the processed and failed folders; "Read-only mailbox access" is replaced by a requirement that fetching stays non-destructive but a separate move step relocates handled messages.
- `refresh-api`: a refresh moves parsed emails to the processed folder and failed emails to the failed folder (replacing "Mailbox is not modified"); a failed move produces HTTP 502.

## Impact

- Code: `api/email_parser/loading/config.py` (new settings), `imap.py` (move method), `api/main.py` (call the move step after `load_and_parse`). `pipeline.py` is unchanged, since moving stays outside `load_and_parse`.
- Tests: `tests/loading/imap_fakes.py` (`FakeIMAP` needs COPY/STORE/EXPUNGE), `test_config.py`, `test_imap.py`, `tests/api/test_main.py`; coverage must stay at 100%.
- Specs: delta specs for `email-loader` and `refresh-api`.
- Operations: the processed and failed folders/labels must exist in the mailbox before running a refresh. No new dependencies.
