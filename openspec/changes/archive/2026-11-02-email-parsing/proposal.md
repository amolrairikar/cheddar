## Why

Cheddar derives income, expenses, and investments from financial emails. Before any fetching or storage can exist, it needs a reliable way to turn an email into structured data, and one that new banks and brokerages can be added to without touching existing code.

## What Changes

- Add a stdlib-only Python package `email_parser.parsing` that converts an already-fetched email into a `Transaction` or an investment `PositionSummary`.
- Add an extensible parser framework: a parser base class, a registry that selects parsers by sender, and a decorator for registering new ones.
- Add HTML-to-text conversion so table-based HTML emails can be parsed line by line.
- Add parsers for Chase, American Express, Capital One, Venmo, and Fidelity.
- Add project scaffolding (`pyproject.toml`, uv-managed environment, pytest with warnings as errors).
- Out of scope: email fetching (IMAP/Gmail), storage, categorization, and any API or UI.

## Capabilities

### New Capabilities
- `email-parser-framework`: the email input model, parsed output models, sender-based parser selection, error semantics, and the extension contract for adding institutions.
- `institution-parsers`: the supported email shapes for Chase, American Express, Capital One, Venmo, and Fidelity and the transactions or position summaries each yields.

### Modified Capabilities
<!-- None: this is the first change in the repository. -->

## Impact

- New code: `api/email_parser/parsing/` and `tests/`.
- New files: `pyproject.toml`, `uv.lock`.
- No runtime dependencies; `pytest` is a dev dependency.
- Parsers are written against synthetic emails. Redacted real samples are still to be supplied and may require regex adjustments.
