## 1. Dependencies and setup

- [x] 1.1 Add `fastapi` and `uvicorn` to `[project].dependencies` and `httpx2` to the dev extra in `pyproject.toml`; run `uv lock` and verify `uv sync --extra dev --locked` succeeds
- [x] 1.2 Ensure `api` is on pytest's `pythonpath` and verify `import main` works from a test

## 2. Response schemas

- [x] 2.1 Create `api/schemas.py` with pydantic models for health, failed entries, parsed entries (with `type` discriminator for transaction vs position summary) and the refresh response; verify with a test that Decimal and datetime values serialize

## 3. Endpoints

- [x] 3.1 Create `api/main.py` with the FastAPI app and `GET /health`; verify the health test returns 200 `{"status": "ok"}` with no mail credentials set
- [x] 3.2 Add `POST /refresh_transactions` as a plain `def` handler that runs `ImapConfig.from_env()`, `ImapLoader` and `load_and_parse` and returns counts, `parsed` and `failed`; verify tests for a transaction, a position summary, a failed entry and an empty mailbox
- [x] 3.3 Add error mapping: `LoaderConfigError` -> 500, other `LoaderError` -> 502, with no credentials in the body; verify tests for missing env, login failure, and folder select/search failure
- [x] 3.4 Add the non-blocking `threading.Lock` guard returning 409, released in `finally`; verify tests for 409 (pipeline not invoked) and that the next request succeeds after success, after 500 and after 502

## 4. Test safety

- [x] 4.1 Add an autouse fixture in `tests/api/test_main.py` that replaces `imaplib.IMAP4_SSL` with `FakeIMAP`, makes real `socket.connect` raise `AssertionError`, and sets dummy `CHEDDAR_IMAP_USER` / `CHEDDAR_IMAP_PASSWORD`; verify a test that an unstubbed IMAP connection attempt fails and that real shell credentials are not used

## 5. Verification

- [x] 5.1 Run `uv run ruff check .` and `uv run pytest --cov --cov-report=term-missing` and verify all tests pass with coverage at 100%
- [x] 5.2 Manually run `uv run uvicorn main:app --app-dir api`, then verify `curl localhost:8000/health` returns ok, `/docs` loads, and `POST /refresh_transactions` returns 500 with env unset
