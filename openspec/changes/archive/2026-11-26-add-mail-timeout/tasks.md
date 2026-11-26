## 1. Timeout and reconnect

- [x] 1.1 In `api/email_parser/loading/imap.py`, create connections with a 30-second timeout constant; verify with a test that the connection is created with that value and that a timeout while connecting or logging in raises `LoaderError` without the password
- [x] 1.2 Extend the fake mail server in `tests/loading/imap_fakes.py` so a test can break one connection while later ones work, make a reconnect fail, and set UIDVALIDITY; verify a broken fake connection rejects every later command
- [x] 1.3 When a fetch raises `OSError` or `imaplib.IMAP4.abort`, record a download failure, shut down the connection without logout and reconnect to the pending folder read-only; do not reconnect for other `imaplib.IMAP4.error` errors. Verify with tests for a mid-batch and a last-message failure that no command follows on the old connection and that `move` uses the new one
- [x] 1.4 Raise `LoaderError` when reconnecting fails or UIDVALIDITY changes; verify with tests for connect, login and select failures and for a changed UIDVALIDITY
- [x] 1.5 Raise `LoaderError` on the third consecutive broken fetch; verify with tests that 3 in a row raise and that 3 separated by successful fetches do not
- [x] 1.6 Replace the comment about relying on the later move to fail, and update the current dropped-connection and fetch `OSError` tests to the new behavior; verify `tests/loading` passes

## 2. Download failures and endpoint behavior

- [x] 2.1 In `imap.py` and `pipeline.py`, distinguish download failures (raised error, non-OK status or no content) from decoding failures, record on `FailedEntry` whether the message was downloaded, and give each its own reason; verify with loader and pipeline tests for each case
- [x] 2.2 In `api/main.py`, move only downloaded failures to the failed folder; verify with tests that each kind of download failure returns 200, is listed in `failed` and stays pending, that a decoding or parse failure still moves to the failed folder, and that a later refresh saves and moves a previously undownloaded email
- [x] 2.3 Add a test that one broken fetch with a successful reconnect returns 200, saves and moves the other emails and leaves that one pending; verify it passes
- [x] 2.4 Add tests that a failed reconnect (before and after a parsed email) and 3 consecutive broken fetches return 502 with no password in the body, save nothing and move nothing, and that the next refresh succeeds; verify they pass
- [x] 2.5 Update `README.md` to say that only downloaded emails that fail move to `transactions-failed`, and that emails that cannot be downloaded stay pending for the next refresh; verify the text matches the `refresh-api` delta

## 3. Verification

- [x] 3.1 With a local server that delays one fetch reply past a shortened timeout and accepts a second connection, run the real `imaplib` through the loader; verify each fetched result holds its own message's content and the move succeeds on the new connection
- [x] 3.2 Run the full test suite and the pre-commit hooks; verify both pass
