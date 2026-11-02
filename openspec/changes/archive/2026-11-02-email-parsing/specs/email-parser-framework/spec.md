## Purpose

Defines how Cheddar turns a fetched email into structured financial data, and how new institutions are added without changing existing parsing code.

## ADDED Requirements

### Requirement: Email input validation
The system SHALL accept an email consisting of a message id, sender, subject, date (UTC ISO 8601), plain-text body, and HTML body, all as strings, and SHALL reject input where any field is missing or not a string with a parse error.

#### Scenario: Valid email
- **WHEN** an email with all six string fields is parsed
- **THEN** parsing proceeds to parser selection

#### Scenario: Malformed email
- **WHEN** an email is supplied with a missing or non-string field
- **THEN** a parse error naming the field is raised

### Requirement: Structured output
Parsing SHALL yield either a transaction (merchant, signed decimal amount, account label, timestamp) or a position summary (account, snapshot date, balance, and positions with ticker, quantity, price, value, account type). Amounts SHALL be exact decimals, negative for money spent or sent and positive for money received. The timestamp SHALL be the email's date.

#### Scenario: Spend is negative
- **WHEN** an email describing a purchase is parsed
- **THEN** the transaction amount is negative

#### Scenario: Income is positive
- **WHEN** an email describing money received is parsed
- **THEN** the transaction amount is positive

### Requirement: Sender-based parser selection
The system SHALL select candidate parsers by matching each parser's declared sender hints, case-insensitively, against the email's sender, and SHALL try candidates in registration order, returning the first non-empty result.

#### Scenario: Sender matches one institution
- **WHEN** an email from a registered institution's address is parsed
- **THEN** only that institution's parser is consulted

#### Scenario: Unsupported sender
- **WHEN** an email from a sender matching no registered parser is parsed
- **THEN** a parse error stating the sender is unsupported is raised

#### Scenario: Supported sender, unrecognized email
- **WHEN** an email from a supported institution matches none of that institution's email shapes
- **THEN** a parse error stating that no parser for that institution matches is raised

### Requirement: Distinguish "not mine" from "malformed"
A parser SHALL report that an email is not a shape it handles by returning no result, and SHALL raise a parse error when the email is a shape it handles but its content is malformed.

#### Scenario: Non-matching shape falls through
- **WHEN** a parser does not recognize the email
- **THEN** the next candidate parser is tried

#### Scenario: Zero amount
- **WHEN** a recognized email states an amount of zero
- **THEN** a parse error is raised

### Requirement: Extensibility without core changes
The system SHALL allow a new institution to be supported by adding a parser that declares its institution name and sender hints and is registered, without modifying the registry or any other institution's parser. Independent registries SHALL be constructible for isolation.

#### Scenario: Add a new institution
- **WHEN** a new parser is registered with its own sender hint
- **THEN** emails from that sender are dispatched to it and existing parsers are unaffected

### Requirement: HTML body as text
The system SHALL convert HTML bodies to text with one block or table cell per line, collapsed whitespace, no empty lines, and script, style, and head content removed, preferring the HTML body and falling back to the plain body when the HTML yields no text.

#### Scenario: Table cells become lines
- **WHEN** an HTML table with two cells in a row is converted
- **THEN** each cell's text appears on its own line

### Requirement: No network access
The parsing layer SHALL operate only on supplied email content and SHALL NOT fetch email or perform network access.

#### Scenario: Offline parsing
- **WHEN** an email is parsed with networking unavailable
- **THEN** parsing behaves identically
