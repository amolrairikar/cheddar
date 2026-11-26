"""Run every case in tests/parsing/cases. Adding a .toml file adds a test."""

from decimal import Decimal

import pytest
from case_files import CASES, case_email, read_case
from email_parser.parsing import (
    InvestmentPosition,
    PositionSummary,
    Transaction,
    default_registry,
    parse_email,
)

PATHS = sorted(CASES.rglob("*.toml"))


def expected_result(expected, date):
    if "positions" not in expected:
        fields = dict(expected, amount=Decimal(expected["amount"]))
        return Transaction(timestamp=date, **fields)

    def position(row):
        numbers = {key: Decimal(row[key]) for key in ("quantity", "price", "value")}
        return InvestmentPosition(account=expected["account"], snapshot_date=date,
                                  **dict(row, **numbers))

    fields = dict(expected, balance=Decimal(expected["balance"]),
                  positions=tuple(position(row) for row in expected["positions"]))
    return PositionSummary(snapshot_date=date, **fields)


@pytest.mark.parametrize(
    "path", PATHS, ids=[p.relative_to(CASES).with_suffix("").as_posix() for p in PATHS])
def test_case(path):
    case = read_case(path)
    assert parse_email(case_email(case)) == expected_result(case["expected"], case["date"])


def test_every_parser_has_a_case():
    covered = {path.parent.name for path in PATHS}
    assert {parser.institution for parser in default_registry.parsers} <= covered
