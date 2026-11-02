## Context

`email_parser.parsing` exposes `Email` (six string fields, date as UTC ISO 8601), `ParseError` and `parse_email`, which returns a `Transaction` or `PositionSummary` or `None`-style "no match" outcomes handled by the registry. Its spec forbids network access, and the project has no runtime dependencies. There is no config or logging pattern yet. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Stdlib-only IMAP loading that is testable without a network.
- A loader that cannot alter the user's mailbox.
- Per-message failure isolation so one bad email never hides the rest.

**Non-Goals:**
- Relabelling or moving messages to `transactions-processed` / `transactions-failed` (a later change; UIDs are returned to enable it).
- Non-IMAP or non-Gmail providers, OAuth, persistence, scheduling.

## Decisions

- **Separate package `email_parser.loading`** (`config.py`, `imap.py`, `pipeline.py`). Keeps network code out of `email_parser.parsing`. Alternative: add to parsing, rejected by its no-network requirement.
- **`imaplib.IMAP4_SSL` + `email.policy.default`.** Matches the no-dependency stance and the existing scripts' use of `email.policy`. Alternative: `imap-tools` / `imapclient`, rejected to avoid a dependency.
- **Read-only access:** `select(folder, readonly=True)`, `UID SEARCH ALL`, `UID FETCH ... (BODY.PEEK[])`. Alternative: normal select and rely on PEEK only; read-only select is the stronger guarantee.
- **Config via a frozen dataclass `ImapConfig`** with `from_env()`; password has `repr=False`. Missing variables raise `LoaderConfigError` listing names only.
- **`message_to_email`** uses `get_body(("plain",))` / `("html",)`, `parsedate_to_datetime` converted to UTC, decoded From header (display name + address) as sender (parsers match on a lowercase substring of it), UID as message-id fallback.
- **`load_and_parse(loader) -> LoadResult`** with `parsed` and `failed` lists of UID-keyed entries; catches `ParseError` and unmatched emails per message. Alternative: raise on first failure, rejected for batch resilience.
- **Logging:** module loggers via `logging.getLogger(__name__)`; bodies at DEBUG, counts at INFO; no handlers configured by the library. Login logging includes only user and host.

## Risks / Trade-offs

- [DEBUG logs contain personal financial data] → DEBUG is opt-in by the caller; INFO and above never log bodies; documented in the README.
- [Gmail IMAP must be enabled and requires an app password] → document setup steps; authentication failures raise a clear `LoaderError`.
- [Fetching ALL messages each run reprocesses everything in the folder] → acceptable since the folder is a pending queue; relabelling in a later change will drain it.
- [Odd or malformed MIME/Date headers] → conversion errors are recorded as per-message failures rather than aborting the batch.
