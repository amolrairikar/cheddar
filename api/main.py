"""FastAPI app exposing the email load/parse pipeline."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import closing

import db
from email_parser.loading import (
    ImapConfig,
    ImapLoader,
    LoaderConfigError,
    LoaderError,
    LoadResult,
    load_and_parse,
)
from email_parser.parsing import PositionSummary
from fastapi import FastAPI, HTTPException
from schemas import HealthResponse, RefreshResponse

app = FastAPI(title="cheddar")

_refresh_lock = threading.Lock()


def _persist(loaded: LoadResult) -> None:
    """Save every parsed result in one database transaction (all or nothing)."""
    try:
        with closing(db.connect(db.db_path())) as conn, conn:
            for entry in loaded.parsed:
                if isinstance(entry.result, PositionSummary):
                    db.save_position_summary(conn, entry.result)
                else:
                    db.save_transaction(conn, entry.result, entry.message_id)
    except (sqlite3.Error, OSError) as exc:
        raise HTTPException(
            status_code=500, detail="could not save results to the database") from exc


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
            _persist(loaded)
            cfg = loader.config
            loader.move([e.uid for e in loaded.parsed], cfg.processed_folder)
            loader.move([e.uid for e in loaded.failed], cfg.failed_folder)
    except LoaderConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except LoaderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        _refresh_lock.release()
    return RefreshResponse.from_load_result(loaded)
