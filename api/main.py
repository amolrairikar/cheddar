"""FastAPI app exposing the email load/parse pipeline."""

from __future__ import annotations

import threading

from email_parser.loading import (
    ImapConfig,
    ImapLoader,
    LoaderConfigError,
    LoaderError,
    load_and_parse,
)
from fastapi import FastAPI, HTTPException
from schemas import HealthResponse, RefreshResponse

app = FastAPI(title="cheddar")

_refresh_lock = threading.Lock()


@app.get("/health")
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/refresh_transactions")
def refresh_transactions() -> RefreshResponse:
    if not _refresh_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="a refresh is already in progress")
    try:
        with ImapLoader(ImapConfig.from_env()) as loader:
            loaded = load_and_parse(loader)
    except LoaderConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except LoaderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        _refresh_lock.release()
    return RefreshResponse.from_load_result(loaded)
