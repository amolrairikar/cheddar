## Context

`ImapLoader.fetch_raw` opens the pending folder with `readonly=True` and fetches with `BODY.PEEK`, so the mailbox is never changed. `load_and_parse` returns a `LoadResult` of `ParsedEntry` / `FailedEntry` (each carrying the IMAP `uid`), and `POST /refresh_transactions` in `api/main.py` runs both inside the `_refresh_lock` and maps `LoaderConfigError` to 500 and other `LoaderError`s to 502. See proposal.md for motivation.

The follow-up `sqlite-persistence` change needs to persist parsed results and only then move emails, so a DB failure leaves the emails in the pending folder for retry.

## Goals / Non-Goals

**Goals:**
- Provide a move step on `ImapLoader` that is independent of fetching and parsing.
- Have the refresh endpoint move parsed emails to the processed folder and failed emails to the failed folder.
- Keep `load_and_parse` free of mailbox side effects.

**Non-Goals:**
- SQLite persistence (separate change).
- Creating the destination folders automatically.
- Retrying a partially completed move.

## Decisions

**1. Separate `ImapLoader.move(uids, destination)` method, called from `main.py`.**
`load_and_parse` stays a pure fetch + parse function; the API calls `loader.move(...)` once for parsed UIDs and once for failed UIDs. Alternative: move inside `load_and_parse`. Rejected because the persistence change must run between parsing and moving, and because a pure pipeline stays easy to test.

**2. Move with COPY + `\Deleted` + EXPUNGE rather than IMAP `MOVE`.**
`conn.uid("COPY", ...)`, then `conn.uid("STORE", ..., "+FLAGS", r"(\Deleted)")`, then `conn.expunge()`. This works on any IMAP server, including those without RFC 6851 `MOVE`, and the stdlib `imaplib` has no dedicated MOVE helper. On Gmail, copying to a label folder adds the label and deleting from the pending label folder removes it. Alternative: `UID MOVE` when the server advertises the `MOVE` capability. Rejected for now to avoid two code paths that both need tests.

**3. Re-select the pending folder read-write inside `move`.**
`fetch_raw` selects read-only, which forbids STORE/EXPUNGE. `move` selects the pending folder read-write itself, so callers don't need to manage session state. UIDs stay valid because they are stable within the same folder and `UIDVALIDITY`, and the whole refresh happens in one connection under `_refresh_lock`.

**4. Copy first, delete only after copy succeeds.**
If COPY returns a non-OK status (for example, the destination folder does not exist), `move` raises `LoaderError` naming the destination folder before any `\Deleted` flag is set, so no email is lost. COPY and STORE are sent as one comma-separated UID set, so a call is all-or-nothing from the client's side. An empty UID list returns early without touching the server.

**5. Destination folders come from `ImapConfig`.**
Add `processed_folder` and `failed_folder` fields, read from `CHEDDAR_IMAP_PROCESSED_FOLDER` / `CHEDDAR_IMAP_FAILED_FOLDER`, with the defaults `transactions-processed` / `transactions-failed`, following the existing `folder` pattern.

**6. Order in the endpoint: load -> parse -> move parsed -> move failed.**
Both moves run inside the same `with ImapLoader(...)` block and the same lock. A `LoaderError` from a move becomes 502 through the existing handler.

## Risks / Trade-offs

- [Plain `EXPUNGE` removes every message flagged `\Deleted` in the folder, not just ours] -> Acceptable for a dedicated pending folder; use `UID EXPUNGE` only if a later need arises.
- [A move that fails after the first of two calls leaves parsed emails moved but failed emails still pending] -> The next refresh picks up the leftovers; no data is lost because nothing is deleted before its copy succeeds.
- [A message that could not be fetched is moved to the failed folder without ever being read] -> Intended, since it is reported in `failed`; the user can inspect it manually.
- [Destination folders missing at runtime] -> Surfaces as a 502 naming the folder; documented as an operational prerequisite in the proposal.
- [Without persistence, a moved email's parsed data exists only in that response] -> Accepted for this interim step; the `sqlite-persistence` change closes the gap and reorders to parse -> persist -> move.
