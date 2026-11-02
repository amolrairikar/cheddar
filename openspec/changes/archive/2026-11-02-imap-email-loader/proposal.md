## Why

The parsing layer turns emails into transactions and position summaries, but nothing fetches emails. The app is local-first and its data comes from a mailbox, so we need a loader that reads that mailbox over IMAP with an email address and app password and feeds the messages to the existing parsers.

## What Changes

- Add a stdlib-only loader that connects to an IMAP server (Gmail by default) with a user email and app password.
- Read messages from the Gmail `transactions-pending` label (configurable), without modifying the mailbox.
- Convert each fetched message into the parsing layer's `Email` model.
- Run each loaded email through `parse_email` and report parsed results and per-message failures without aborting the batch.
- Read credentials and connection settings from environment variables.
- Log fetched email contents at DEBUG for troubleshooting, and never log the app password.
- Document the configuration in the README.

## Capabilities

### New Capabilities
- `email-loader`: Fetching emails from an IMAP mailbox, converting them to the parsing `Email` model, parsing them, and reporting results, with environment-based configuration and debug logging.

### Modified Capabilities

## Impact

- New package `api/email_parser/loading/` and tests under `tests/loading/`.
- Reuses `Email`, `ParseError` and `parse_email` from `email_parser.parsing`; the parsing layer stays free of network access.
- No new runtime dependencies (`imaplib`, `email`, `logging` from the standard library).
- `README.md` gains configuration documentation (docs-only).
- Out of scope: relabelling or moving messages after processing, storage, categorization, and non-IMAP providers.
