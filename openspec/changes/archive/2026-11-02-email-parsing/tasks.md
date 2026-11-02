## 1. Project setup

- [x] 1.1 Add `pyproject.toml` (package `cheddar`, Python >=3.11, no runtime deps, pytest dev extra, warnings as errors) and verify `uv sync --extra dev` succeeds
- [x] 1.2 Create a uv-managed environment and verify `uv run pytest` runs

## 2. Framework

- [x] 2.1 Implement models (`Email`, `Transaction`, `InvestmentPosition`, `PositionSummary`, `ParseError`) and verify malformed input raises `ParseError`
- [x] 2.2 Implement `html_to_text` / `email_text` and verify `tests/parsing/test_text.py` passes
- [x] 2.3 Implement `EmailParser` base class and `ParserRegistry` with `@register`, and verify `tests/parsing/test_registry.py` passes (unsupported sender, no matching shape, new-institution extensibility)
- [x] 2.4 Add shared parser helpers (amount parsing, zero check, whitespace normalization) and verify via parser tests

## 3. Institution parsers

- [x] 3.1 Chase parser (deposit, transfer, card alert) with passing tests
- [x] 3.2 American Express parser with passing test
- [x] 3.3 Capital One parser (including wrapped lines) with passing test
- [x] 3.4 Venmo parser (paid, received) with passing tests
- [x] 3.5 Fidelity parser (table parsing, total validation) with passing tests

## 3b. Venmo request payments

- [x] 3b.1 Extend the Venmo parser to accept "<name> paid your $N request" as a positive transaction and verify a new unit test in `tests/parsing/test_parsers.py` passes
- [x] 3b.2 Add `tests/fixtures/venmo/payment_sent.eml` and `payment_received.eml` (redacted: fake counterparty name, example.com Message-IDs) and verify fixture tests in `tests/parsing/test_fixtures.py` parse both to the expected transactions

## 4. Real-sample validation

- [x] 4.1 Add user-supplied redacted real emails for each institution under `tests/fixtures/<institution>/` and verify files exist
- [x] 4.2 Add fixture-driven tests per parser, adjust regexes where real formats differ, and verify `uv run pytest` passes

## 5. Documentation

- [x] 5.1 Document in `README.md` how to request a new institution via the issue template (`.github/ISSUE_TEMPLATE/new-institution.md`) and verify the link resolves to the template
