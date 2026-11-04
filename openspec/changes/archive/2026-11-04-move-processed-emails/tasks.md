## 1. Configuration

- [x] 1.1 Add `DEFAULT_PROCESSED_FOLDER` / `DEFAULT_FAILED_FOLDER` and `processed_folder` / `failed_folder` fields to `ImapConfig` in `api/email_parser/loading/config.py`, read from `CHEDDAR_IMAP_PROCESSED_FOLDER` / `CHEDDAR_IMAP_FAILED_FOLDER`; verify with new cases in `tests/loading/test_config.py` (defaults and overrides) passing

## 2. Loader move step

- [x] 2.1 Extend `FakeIMAP` in `tests/loading/imap_fakes.py` to support read-write `select`, `uid("COPY")`, `uid("STORE")` with `\Deleted`, and `expunge()` across multiple folders; verify the existing loader tests still pass
- [x] 2.2 Add `ImapLoader.move(uids, destination)` in `api/email_parser/loading/imap.py` (select pending folder read-write, COPY, STORE `\Deleted`, EXPUNGE; early return on empty list; `LoaderError` naming the destination when COPY fails or the loader is not connected); verify with tests in `tests/loading/test_imap.py` covering move, untouched siblings, empty list, missing destination (messages remain pending) and not-connected
- [x] 2.3 Update the `ImapLoader` docstring and module docstring in `imap.py` to say fetching is non-destructive and moving is a separate step; verify `uv run ruff check .` passes

## 3. Refresh endpoint

- [x] 3.1 In `api/main.py`, after `load_and_parse` and inside the same `with ImapLoader(...)` block, call `loader.move` for parsed UIDs to the processed folder and for failed UIDs to the failed folder; verify with `tests/api/test_main.py` cases showing emails land in the right folders
- [x] 3.2 Add `tests/api/test_main.py` cases for a missing destination folder returning 502 with the folder named, and for a second refresh returning zero counts; verify they pass
- [x] 3.3 Verify no `load_and_parse` behavior changed: `tests/loading/test_pipeline.py` passes unmodified

## 4. Wrap-up

- [x] 4.1 Run `uv run ruff check .` and `uv run pytest --cov --cov-report=term-missing`; verify both are clean with 100% coverage
- [x] 4.2 Update `README.md` with the new env vars and the requirement that the processed and failed folders exist; verify the README mentions `CHEDDAR_IMAP_PROCESSED_FOLDER` and `CHEDDAR_IMAP_FAILED_FOLDER`
