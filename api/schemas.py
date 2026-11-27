"""Response models for the HTTP API."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from email_parser.loading import LoadResult
from email_parser.parsing.models import ParseResult, PositionSummary
from pydantic import BaseModel, ConfigDict, Field, StringConstraints


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


class TransactionItem(BaseModel):
    id: int
    original_merchant: str
    original_amount: str
    merchant: str
    amount: str
    account: str
    transaction_timestamp: str
    category: str | None
    transaction_type: Literal["Income", "Expense"] | None
    tags: list[str]
    deleted_at: str | None


class TransactionListResponse(BaseModel):
    transactions: list[TransactionItem]


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TransactionUpdate(BaseModel):
    """The fields to change; omitted ones stay as they are. Other fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    # The constraint changes no valid value, but makes Pydantic reject text that is not
    # valid Unicode, which could not be stored.
    merchant: Annotated[str, StringConstraints(min_length=0)] | None = None
    # The digit limit stops a huge exponent from expanding into a huge stored string.
    amount: Annotated[Decimal, Field(max_digits=20)] | None = None
    category: NonBlank | None = None
    transaction_type: Literal["Income", "Expense"] | None = None
    # Not nullable: [] removes all tags.
    tags: list[NonBlank] = Field(default_factory=list)

    def changes(self) -> dict[str, object]:
        """Only the fields the client sent, with the amount in plain notation."""
        changes = self.model_dump(exclude_unset=True)
        if changes.get("amount") is not None:
            changes["amount"] = format(changes["amount"], "f")
        return changes


class DeleteRequest(BaseModel):
    ids: list[int]


class DeleteResponse(BaseModel):
    deleted: list[int]
    not_found: list[int]
