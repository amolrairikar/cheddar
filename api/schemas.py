"""Response models for the HTTP API."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from email_parser.loading import LoadResult
from email_parser.parsing.models import ParseResult, PositionSummary
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class _FromDataclass(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TransactionResult(_FromDataclass):
    type: Literal["transaction"] = "transaction"
    merchant: str
    amount: Decimal
    account: str
    timestamp: str


class PositionOut(_FromDataclass):
    ticker: str
    quantity: Decimal
    price: Decimal
    value: Decimal
    account: str
    account_type: str
    snapshot_date: str


class PositionSummaryResult(_FromDataclass):
    type: Literal["position_summary"] = "position_summary"
    account: str
    snapshot_date: str
    balance: Decimal
    positions: list[PositionOut]


Result = Annotated[TransactionResult | PositionSummaryResult, Field(discriminator="type")]


def _result(result: ParseResult) -> TransactionResult | PositionSummaryResult:
    if isinstance(result, PositionSummary):
        return PositionSummaryResult.model_validate(result)
    return TransactionResult.model_validate(result)


class ParsedItem(BaseModel):
    uid: str
    result: Result


class FailedItem(BaseModel):
    uid: str
    reason: str


class RefreshResponse(BaseModel):
    parsed_count: int
    failed_count: int
    parsed: list[ParsedItem]
    failed: list[FailedItem]

    @classmethod
    def from_load_result(cls, loaded: LoadResult) -> RefreshResponse:
        return cls(
            parsed_count=len(loaded.parsed),
            failed_count=len(loaded.failed),
            parsed=[ParsedItem(uid=e.uid, result=_result(e.result)) for e in loaded.parsed],
            failed=[FailedItem(uid=e.uid, reason=e.reason) for e in loaded.failed],
        )
