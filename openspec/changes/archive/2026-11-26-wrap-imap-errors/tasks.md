## 1. Loader error handling

- [x] 1.1 In `api/email_parser/loading/imap.py`, also convert `OSError` from folder selection into `LoaderError`; verify with a test in `tests/loading/test_imap.py` that the error names the folder
- [x] 1.2 Convert `imaplib.IMAP4.error` and `OSError` from the search call into `LoaderError` naming the pending folder; verify with a test for each error type
- [x] 1.3 Catch `imaplib.IMAP4.error` and `OSError` from each fetch call, log a warning with the exception details and record that message as failed; verify with tests that one error of each type leaves the other messages fetched, that a dropped connection fails all remaining messages, and that the existing non-OK fetch test still passes
- [x] 1.4 Also convert `OSError` from copy, flag and expunge in `move` into `LoaderError` naming the destination; verify with a test for each of the three calls

## 2. Endpoint behavior

- [x] 2.1 Add a test in `tests/api/test_main.py` that one fetch error on a working connection returns 200, lists and moves that email as failed, and saves and moves the others; verify it passes
- [x] 2.2 Add a test that a connection dropped after one parsed email returns 502 with no password in the body, keeps that email's saved result and moves nothing, and that the next refresh succeeds without duplicate transactions; verify it passes
- [x] 2.3 Add a test that a connection dropped on the first fetch, with no parsed emails, returns 502, saves nothing and moves nothing; verify it passes
- [x] 2.4 Add a test that a connection error during a move returns 502 and keeps the saved rows, and that the next refresh succeeds without duplicate transactions; verify it passes

## 3. Verification

- [x] 3.1 Run the full test suite and the pre-commit hooks; verify both pass
