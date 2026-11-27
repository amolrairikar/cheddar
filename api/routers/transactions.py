"""Endpoints for listing, editing and soft-deleting stored transactions."""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from datetime import date
from typing import Annotated, Literal

import db
from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BeforeValidator, StringConstraints
from schemas import (
    DeleteRequest,
    DeleteResponse,
    TransactionItem,
    TransactionListResponse,
    TransactionUpdate,
)

router = APIRouter()


def _require_date_format(value: str) -> str:
    # On its own, ``date`` also accepts Unix timestamps and datetimes.
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("date must be in YYYY-MM-DD format")
    return value


DateFilter = Annotated[date | None, BeforeValidator(_require_date_format)]
TextFilter = Annotated[list[Annotated[str, StringConstraints(pattern=r"\S")]] | None, Query()]
TypeFilter = Annotated[list[Literal["Income", "Expense"]] | None, Query()]
# The upper bound is SQLite's largest integer; larger ones would overflow.
TransactionId = Annotated[int, Path(ge=1, le=2**63 - 1)]


@router.get("/transactions")
def list_transactions(
    deleted: bool = False,
    start_date: DateFilter = None,
    end_date: DateFilter = None,
    merchant: TextFilter = None,
    category: TextFilter = None,
    account: TextFilter = None,
    tag: TextFilter = None,
    transaction_type: TypeFilter = None,
) -> TransactionListResponse:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must not be after end_date")
    try:
        with closing(db.connect(db.db_path())) as conn:
            items = db.list_transactions(
                conn, deleted, start_date=start_date, end_date=end_date, merchants=merchant,
                categories=category, accounts=account, tags=tag,
                transaction_types=transaction_type)
    except (sqlite3.Error, OSError) as exc:
        raise HTTPException(
            status_code=500, detail="could not read transactions from the database") from exc
    return TransactionListResponse(transactions=items)


@router.patch("/transactions/{transaction_id}")
def update_transaction(
    transaction_id: TransactionId, update: TransactionUpdate
) -> TransactionItem:
    try:
        with closing(db.connect(db.db_path())) as conn, conn:
            item = db.update_transaction(conn, transaction_id, update.changes())
    except (sqlite3.Error, OSError) as exc:
        raise HTTPException(
            status_code=500, detail="could not update the transaction in the database") from exc
    if item is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    return TransactionItem(**item)


@router.delete("/transactions")
def delete_transactions(request: DeleteRequest) -> DeleteResponse:
    try:
        with closing(db.connect(db.db_path())) as conn, conn:
            deleted = db.soft_delete_transactions(conn, request.ids)
    except (sqlite3.Error, OSError) as exc:
        raise HTTPException(
            status_code=500, detail="could not delete transactions from the database") from exc
    not_found = [i for i in dict.fromkeys(request.ids) if i not in deleted]
    return DeleteResponse(deleted=deleted, not_found=not_found)
