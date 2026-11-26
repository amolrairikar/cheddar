## Context

`ImapLoader` creates its connection without a timeout. `fetch_raw` catches `(imaplib.IMAP4.error, OSError)` for each fetch and continues on the same connection, and relies on a broken connection also failing the later move. A download failure and a decoding failure are both returned as `(None, uid)`, and the refresh moves every failed email to the failed folder. See proposal.md for motivation.

A read timeout breaks that assumption. With a local server that delayed one reply past the client timeout, `imaplib` on Python 3.14 kept the connection usable: the next fetch received the delayed message's data, and a move then succeeded. So after an error of this kind the connection's replies can no longer be trusted.

## Goals / Non-Goals

**Goals:**
- No single wait on the mail server is unbounded.
- No command is sent on a connection after it has broken.
- One email that breaks the connection does not stop the others from being processed.
- An email that was not downloaded stays pending.

**Non-Goals:**
- A deadline for the whole refresh. A server that keeps sending data slowly can still take longer than 30 seconds.
- A configurable timeout.
- Retrying the email whose fetch failed, backoff delays, or reconnecting during select, search or move.

## Decisions

**Pass a 30-second timeout when creating the connection.** `IMAP4_SSL` applies it to connecting and to each later socket operation. A module constant holds the value. A timer around the whole refresh was rejected because a large mailbox can legitimately take a long time.

**Classify fetch errors by whether the connection survives.** `OSError` (which includes timeouts and TLS errors) and `imaplib.IMAP4.abort` mean broken. Any other `imaplib.IMAP4.error` is a complete reply, so only that message fails. `abort` subclasses `error`, so it must be caught first. Treating every `OSError` as broken may reconnect when not strictly needed, which costs only a login.

**Reconnect once per broken fetch, and do not retry that message.** The loader records a download failure for the message, shuts the old socket down without sending `LOGOUT` (which would read stale replies and could wait for another timeout), connects and logs in, and selects the pending folder read-only. It then continues with the next UID, and `move` uses the new connection. If this happens on the last message, it still reconnects so that the move can run. Retrying the same message was rejected because a message that always times out would use up the retries.

**Check UIDVALIDITY after reconnecting.** The remaining UIDs are only meaningful if the folder's UIDVALIDITY matches the value from the first selection. If it differs, raise `LoaderError`.

**Stop after 3 broken fetches in a row.** This bounds the time spent waiting and logging in again when the server accepts logins but every fetch breaks the connection. The count resets whenever a fetch gets a reply on a working connection. At the limit, raise `LoaderError`.

**Mark download failures through to the endpoint.** `fetch_raw` reports a download failure (a raised error, a non-OK status or no message content) differently from a decoding failure, and `FailedEntry` records whether the message was downloaded. `api/main.py` moves only downloaded failures to the failed folder. Both kinds stay in the response's `failed` list and `failed_count`, so the response shape does not change. A separate result list for download failures was rejected because it would add little over one flag.

**When the refresh stops, raise from `fetch_raw`.** Nothing is saved or moved, so all emails stay pending. Returning partial results to save first was rejected: it needs a way to report both results and a failure, and the next refresh will process those emails anyway.

## Risks / Trade-offs

- [A message that always fails to download stays pending and is reported on every refresh] → Accepted. This is expected to be rare, and it remains visible in the `failed` list.
- [3 consecutive messages that each always break the connection would block every refresh] → Expected to be very unlikely. It returns a visible 502 and no mail is lost.
- [Waits add up: each broken fetch can take 30 seconds plus a reconnect] → The consecutive limit bounds a total outage, but not many separated failures.
- [A move that times out may have succeeded on the server] → Same as other failed moves. Stored transactions are not duplicated.
