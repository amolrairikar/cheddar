## Why

The mail connection has no timeout, so an unresponsive server can leave a refresh waiting indefinitely, and every later refresh gets 409. Adding a timeout alone is unsafe: in a local test, the loader reused a connection after a fetch timed out, the late reply for email 2 was returned for email 3, and the following move succeeded. In a refresh, that could mark email 3 processed without saving its transaction.

## What Changes

- Every wait on the mail server, including while connecting, is limited to a fixed 30 seconds. It is not configurable and does not limit the total length of a refresh.
- When a fetch times out or otherwise breaks the connection, that email is reported as failed, and the loader opens a new connection before fetching the next one. A broken connection is never reused.
- Changed from current behavior: an email that cannot be downloaded, for any reason, stays in the pending folder so a later refresh tries it again. Only emails that were downloaded but cannot be decoded or parsed move to the failed folder.
- The failure reason now says whether the email could not be downloaded or could not be decoded.
- The refresh stops with 502, saving and moving nothing, if reconnecting fails, if the mailbox's message identifiers are no longer valid after reconnecting, or if 3 fetches in a row break the connection.
- Changed from current behavior: a connection that drops during fetching no longer fails all remaining emails.
- Unchanged: an error reply that leaves the connection usable does not stop the other fetches or cause a reconnect. Timeouts while logging in, selecting, searching or moving produce 502.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `email-loader`: adds the timeout, changes how fetch errors that break the connection are handled, and distinguishes download failures from other failures.
- `refresh-api`: keeps emails that cannot be downloaded in the pending folder, and changes the outcome of a refresh when the connection breaks during fetching.

## Impact

- `api/email_parser/loading/imap.py` (connection setup and `fetch_raw`), `api/email_parser/loading/pipeline.py` and `api/main.py` (which failed emails are moved).
- `README.md`: which failed emails move to `transactions-failed`.
- `tests/loading/` (including the fake mail server) and `tests/api/test_main.py`. Some tests of the current dropped-connection behavior change.
- A refresh against a server that takes over 30 seconds to reply now fails where it previously waited.
- No new dependencies, settings or response body fields.
