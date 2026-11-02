## 1. Configuration

- [x] 1.1 Create `api/email_parser/loading/` with `__init__.py`, `config.py` (`ImapConfig`, `from_env()`, `LoaderConfigError`, password hidden from `repr`) and verify tests in `tests/loading/test_config.py` cover defaults, overrides and the missing-variable error (no credential in message)

## 2. IMAP loader

- [x] 2.1 Implement `message_to_email` in `imap.py` and verify tests cover multipart bodies, UTC date normalization, display-name sender, empty missing bodies and the UID fallback for a missing Message-ID
- [x] 2.2 Implement `ImapLoader` (context manager, TLS login, read-only select, `UID SEARCH ALL`, `UID FETCH BODY.PEEK[]`, `LoadedEmail`, `LoaderError`) and verify tests with a fake `IMAP4_SSL` assert read-only select, PEEK fetch, login failure and missing-folder errors

## 3. Pipeline

- [x] 3.1 Implement `load_and_parse` and `LoadResult` in `pipeline.py` and verify tests cover a mixed batch (parsed, `ParseError`, unrecognized) and an empty folder

## 4. Logging

- [x] 4.1 Add DEBUG (headers, bodies, parse outcome) and INFO (counts) logging across the loader and pipeline, and verify `caplog` tests show contents at DEBUG, no bodies at INFO, and the password absent from all records including after a failed login

## 5. Docs and verification

- [x] 5.1 Document `CHEDDAR_IMAP_*` variables, Gmail IMAP and app-password setup, and DEBUG logging in `README.md` and verify the section renders and names every variable
- [x] 5.2 Run `uv run pytest` and verify the whole suite passes with warnings as errors

## 6. Lint

- [x] 6.1 Resolve ruff UP017 in `api/email_parser/loading/imap.py` by replacing `from datetime import timezone` and both `timezone.utc` usages with `from datetime import UTC` / `UTC`, and verify `uv run ruff check` reports no violations and `uv run pytest` still passes
