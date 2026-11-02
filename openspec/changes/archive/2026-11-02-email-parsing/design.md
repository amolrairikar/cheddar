## Context

Greenfield repository; see proposal.md for motivation. This change documents a layer that has already been implemented and tested against synthetic emails. The design ports proven techniques from an existing function-based parser (stdlib-only, `Decimal` amounts, regex per institution) but replaces its hard-coded `if` dispatch chain, which requires editing core code to add an institution.

## Goals / Non-Goals

**Goals:**
- Adding an institution touches one new module plus one import line.
- No runtime dependencies; exact decimal money handling.
- Pure functions of the email content: no I/O.

**Non-Goals:**
- Fetching, storage, deduplication, categorization.
- Parsing transaction dates from bodies (the email date is used).
- Plugin discovery via entry points.

## Decisions

- **Parser classes plus registry, not a dispatch chain.** `EmailParser` declares `institution` and `sender_hints`; `ParserRegistry` filters by sender and tries candidates in order. `@register` adds to a default registry; explicit registries are constructible for tests and plugins. Alternative: keep an if-chain (rejected: closed for extension).
- **Tri-state parse contract.** Return `None` = not my shape; raise `ParseError` = my shape but malformed. This lets one institution have several email shapes tried in order, with the registry raising a clear error if none match.
- **Sender substring matching.** Lowercased substring of the From header (e.g. `chase`, `americanexpress`) is simple and robust to display-name variations. Trade-off: loose; subject/body checks inside each parser provide precision.
- **Stdlib `html.parser` for HTML→text.** Block and table-cell tags emit newlines so a table reads one cell per line, which suits line-anchored regexes. Alternative: BeautifulSoup/lxml (rejected: dependency for little gain).
- **`Decimal` with sign convention.** Spend negative, income positive; zero rejected. Timestamp is the email Date.
- **Frozen dataclasses** for `Email` and outputs; `Email.from_dict` validates raw input.
- **Tooling.** `uv` manages the environment and lockfile; pytest runs with warnings as errors.

## Risks / Trade-offs

- [Parsers were written against synthetic emails, so real formats may differ] → The user will supply redacted real samples for `tests/fixtures/`; adjust regexes against them.
- [Email formats change without notice] → Each parser fails loudly with `ParseError` rather than guessing; narrow regexes with focused tests.
- [Loose sender matching could route unrelated mail to a parser] → Parsers return `None` for unrecognized shapes.
- [Chase transfer alerts name no recipient] → Merchant left blank for later user fill-in.
- [Importing `parsers/__init__` is what registers built-ins] → `email_parser.parsing` imports it; custom registries avoid global state.
