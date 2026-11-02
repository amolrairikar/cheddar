## Why

The email load/parse pipeline in `api/email_parser` has no entry point: callers must compose `ImapConfig`, `ImapLoader` and `load_and_parse` by hand. Exposing it over HTTP gives the planned application (and any scheduler) a single call to refresh transactions, and a health check to confirm the service is up.

## What Changes

- Add a FastAPI app at `api/main.py` (with response models in `api/schemas.py`); no new package.
- Add `GET /health`, returning `200 {"status": "ok"}` without touching IMAP.
- Add `POST /refresh_transactions`, which runs the IMAP load/parse pipeline and returns `parsed_count`, `failed_count`, `parsed` (`[{uid, result}]`) and `failed` (`[{uid, reason}]`).
- Map failures to HTTP errors: `LoaderConfigError` -> 500, any other `LoaderError` -> 502, a refresh already in progress -> 409 (guarded by a `threading.Lock`).
- No authentication in this change.
- Add runtime dependencies `fastapi` and `uvicorn`, and dev dependency `httpx2`; regenerate `uv.lock`.
- Tests must never make live IMAP calls.

## Capabilities

### New Capabilities
- `refresh-api`: HTTP API exposing a health check and a `refresh_transactions` endpoint that runs the email load/parse pipeline, including its response shape and error mapping.

### Modified Capabilities
<!-- None: existing email-loader and parser requirements are unchanged. -->

## Impact

- New code: `api/main.py`, `api/schemas.py`, tests under `tests/api/`.
- Modified: `pyproject.toml`, `uv.lock`. README is not changed.
- Reuses `api/email_parser/loading/{config,imap,pipeline}.py` and `api/email_parser/parsing/models.py` unchanged.
- Run with `uv run uvicorn main:app --app-dir api`.
