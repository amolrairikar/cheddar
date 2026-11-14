"""Endpoints for listing and soft-deleting stored transactions."""

from __future__ import annotations

import sqlite3
from contextlib import closing

import db
from fastapi import APIRouter, HTTPException
from schemas import DeleteRequest, DeleteResponse, TransactionListResponse

router = APIRouter()


@router.get("/transactions")
def list_transactions(deleted: bool = False) -> TransactionListResponse:
    try:
        with closing(db.connect(db.db_path())) as conn:
            items = db.list_transactions(conn, deleted)
    except (sqlite3.Error, OSError) as exc:
        raise HTTPException(
            status_code=500, detail="could not read transactions from the database") from exc
    return TransactionListResponse(transactions=items)


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
