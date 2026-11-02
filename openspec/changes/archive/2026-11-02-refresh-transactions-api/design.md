## Context

The pipeline is `ImapConfig.from_env()` -> `ImapLoader(config)` (a context manager over blocking `imaplib.IMAP4_SSL`) -> `load_and_parse(loader)` -> `LoadResult(parsed, failed)`. Models in `email_parser/parsing/models.py` are frozen dataclasses (`Transaction`, `PositionSummary`) containing `Decimal` and `datetime` values. The loader is read-only and raises `LoaderConfigError` / `LoaderError` with messages that never contain the password. There is no database, so results can only be returned in the response. The repo enforces 100% line and branch coverage and `filterwarnings=error`. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- A thin HTTP layer over the existing pipeline with no changes to `email_parser`.
- Deterministic error mapping and no concurrent IMAP sessions.

**Non-Goals:**
- Persistence, authentication, scheduling, or moving mail between folders.
- Pagination or streaming of results.

## Decisions

- **Flat layout: `api/main.py` and `api/schemas.py`, no `app` package.** `api/` is already the setuptools package root, so top-level modules there need no packaging changes. Run with `uvicorn main:app --app-dir api`; pytest gets `api` on `pythonpath`. Alternative: an `api/app/` package, rejected as unnecessary structure. Subdirectories (e.g. `routers/`) can be added if the API grows.
- **Sync `def` endpoint.** `imaplib` blocks; FastAPI runs plain `def` handlers in a threadpool, so the event loop stays free. Alternative: `async def` with `run_in_threadpool`, which adds code with no benefit.
- **Pydantic response models in `schemas.py`.** Parsed results are converted from the dataclasses with a `type` discriminator (`"transaction"` / `"position_summary"`), so clients can tell the union apart; `Decimal` and `datetime` serialize via pydantic. Alternative: return raw dataclasses, rejected because the union would be ambiguous in the OpenAPI schema.
- **Error mapping.** `LoaderConfigError` -> 500 (server misconfiguration), other `LoaderError` -> 502 (upstream mail server failure). The existing exception messages are used as detail since they exclude credentials. Unexpected exceptions are left to FastAPI's default 500 handler, which does not echo details.
- **Concurrency guard: module-level `threading.Lock`, acquired non-blocking.** Failure to acquire returns 409 immediately; release is in a `finally` so success and every error path free the lock. Alternative: queueing requests, rejected because a second refresh would just re-read the same mailbox. This is per-process; a multi-worker deployment would need a shared lock (see Risks).
- **Dependencies.** `fastapi` and `uvicorn` as runtime dependencies; `httpx2` in the dev extra for `TestClient`. `uv.lock` regenerated so CI's `--locked` passes.
- **Tests never touch IMAP.** An autouse fixture in `tests/api/test_main.py` (not a `conftest.py`: tests are not packages, so a second `conftest` collides with `tests/conftest.py`) replaces `imaplib.IMAP4_SSL` with the existing `FakeIMAP`, makes any real `socket.connect` raise `AssertionError`, and sets dummy `CHEDDAR_IMAP_USER` / `CHEDDAR_IMAP_PASSWORD` with `monkeypatch.setenv` so shell credentials are never used. Tests cover success, 500, 502, 409, and lock release after success and after each error.

## Risks / Trade-offs

- [Lock only protects a single process] -> Run one worker for now; revisit with a shared lock if scaled out.
- [Unauthenticated endpoint that reads a mailbox and returns financial data] -> Bind to localhost / private network only until an auth change is made; auth is an explicit follow-up.
- [Large mailboxes yield large responses and slow requests, since `UID SEARCH ALL` reads everything] -> Accepted for now; paging or a persistent store is a later change.
- [Same emails are returned on every refresh because the loader never moves or flags mail] -> Accepted; folder management is a separate change.
