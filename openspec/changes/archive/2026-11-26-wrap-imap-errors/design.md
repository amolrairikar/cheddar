## Context

`ImapLoader` converts login errors into `LoaderError`, and `api/main.py` maps `LoaderError` to 502. After login, only `imaplib` errors from `select` and the move commands are converted. See proposal.md for motivation.

`imaplib.IMAP4.abort` subclasses `imaplib.IMAP4.error`, and socket and TLS errors subclass `OSError`, so catching `(imaplib.IMAP4.error, OSError)` covers both families. `__enter__` and `_close` already use this pair.

## Goals / Non-Goals

**Goals:**
- Errors raised by folder selection, search and move calls are reported as `LoaderError`, with the original exception chained.
- An error raised by one fetch call never ends the fetch loop.

**Non-Goals:**
- Retries, reconnects or connection timeouts.
- Recovering from a partly completed move.
- Changing how non-OK statuses or undecodable messages are handled.

## Decisions

**Convert errors in the loader, not the endpoint.** Catching `imaplib` and `OSError` in `api/main.py` would leak mail details into the API layer, and an `OSError` catch there could mislabel unrelated failures as mail errors.

**Wrap only the IMAP calls.** The `try` blocks cover server calls, not message conversion, which keeps its existing per-message handling.

**A raised fetch error fails only that message.** `fetch_raw` catches the error around each fetch call, logs a warning with the exception details, and records the message as `(None, uid)`, the same as a non-OK status. The existing failure reason and move to the failed folder then apply. The alternative, aborting the refresh, would let one bad message hold back all the others.

**A dropped connection needs no separate handling.** The remaining fetches also raise and are recorded as failed. Parsed results are saved, then the first move uses the same dead connection and raises `LoaderError`, so the refresh returns 502 and no email is moved. This depends on the loader never reconnecting. If reconnection is added later, connection errors must be told apart from per-message errors, or unfetched emails could be moved to the failed folder.

## Risks / Trade-offs

- [A temporary error on a working connection sends a good email to the failed folder] → Accepted, matching the non-OK fetch behavior. The user can move it back to the pending folder.
- [A message that breaks the connection every time it is fetched makes every refresh return 502] → Accepted. Fixing it needs reconnection, which is out of scope. No mail is lost.
- [A dropped connection logs a warning for every remaining message] → Accepted as noise in a rare case.
- [A move that fails after the copy can leave copies in the destination, and a retry copies them again] → Existing behavior. Stored transactions are not duplicated because the source email ID is unique.
- [If moving parsed emails fails, failed emails are not moved either] → Existing behavior; they stay pending for the next refresh.
