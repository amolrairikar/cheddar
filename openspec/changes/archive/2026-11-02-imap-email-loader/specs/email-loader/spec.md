## Purpose

Defines how Cheddar loads emails from an IMAP mailbox using an email address and app password, converts them to the parsing layer's email model, and runs them through the parsers.

## ADDED Requirements

### Requirement: Configuration from environment
The system SHALL read the IMAP user and app password from the environment variables `CHEDDAR_IMAP_USER` and `CHEDDAR_IMAP_PASSWORD`, and SHALL allow overriding the host and folder via `CHEDDAR_IMAP_HOST` and `CHEDDAR_IMAP_FOLDER`. The defaults SHALL be host `imap.gmail.com` (TLS, port 993) and folder `transactions-pending`. Explicit values supplied by the caller SHALL be usable instead of the environment.

#### Scenario: Required variables present
- **WHEN** `CHEDDAR_IMAP_USER` and `CHEDDAR_IMAP_PASSWORD` are set and the optional variables are not
- **THEN** the configuration uses host `imap.gmail.com`, port 993 and folder `transactions-pending`

#### Scenario: Optional overrides
- **WHEN** `CHEDDAR_IMAP_FOLDER` is set to `INBOX`
- **THEN** the configuration uses folder `INBOX`

#### Scenario: Missing required variable
- **WHEN** `CHEDDAR_IMAP_PASSWORD` is not set
- **THEN** loading the configuration fails with a configuration error that names the missing variable and does not include any credential value

### Requirement: Read-only mailbox access
The system SHALL connect over TLS, authenticate with the configured credentials, and fetch every message in the configured folder without changing the mailbox: it SHALL NOT mark messages as read, move, label, flag or delete them.

#### Scenario: Fetch leaves mailbox unchanged
- **WHEN** emails are fetched from the configured folder
- **THEN** the folder is opened read-only and message bodies are fetched without setting the seen flag

#### Scenario: Authentication failure
- **WHEN** the server rejects the credentials
- **THEN** the system raises a loader error and the message does not contain the password

#### Scenario: Folder does not exist
- **WHEN** the configured folder cannot be selected
- **THEN** the system raises a loader error naming the folder

### Requirement: Conversion to the email model
The system SHALL convert each fetched message into the parsing layer's `Email` with string values for message id, sender, subject, date, plain-text body and HTML body. The sender SHALL be the decoded From header, including any display name and the address (surrounding quotes around the display name MAY be dropped). The date SHALL be normalized to UTC ISO 8601. A missing body part SHALL yield an empty string. When a message has no Message-ID header, the message's IMAP UID SHALL be used as its message id.

#### Scenario: Multipart message
- **WHEN** a message has both text/plain and text/html parts
- **THEN** the resulting email has both bodies populated

#### Scenario: Date normalization
- **WHEN** a message has the Date header `Thu, 29 Oct 2026 18:01:51 -0400`
- **THEN** the resulting email date is `2026-10-29T22:01:51+00:00`

#### Scenario: Display-name sender
- **WHEN** the From header is `"Capital One | Venture X" <capitalone@notification.capitalone.com>`
- **THEN** the resulting email sender is `Capital One | Venture X <capitalone@notification.capitalone.com>`

#### Scenario: Missing Message-ID
- **WHEN** a message has no Message-ID header
- **THEN** the resulting email message id is the message's IMAP UID

### Requirement: Parse loaded emails
The system SHALL pass each loaded email through the existing parsers and return, for every message, its IMAP UID together with either the parsed result or a failure reason. A message that no parser recognizes, or whose parser raises a parse error, SHALL be recorded as failed and SHALL NOT prevent the remaining messages from being processed.

#### Scenario: Mixed batch
- **WHEN** a batch contains one parsable email, one malformed email for a known institution, and one email no parser recognizes
- **THEN** the result contains one parsed entry and two failed entries, each identified by UID

#### Scenario: Empty folder
- **WHEN** the folder contains no messages
- **THEN** the result has no parsed and no failed entries

### Requirement: Debug logging
The system SHALL log fetched email contents at DEBUG level for troubleshooting: each message's UID, message id, sender, subject, date and full plain-text and HTML bodies, plus the parse outcome per UID. The system SHALL log summary counts at INFO level. The system SHALL NOT log the app password at any level, and SHALL NOT configure logging handlers itself.

#### Scenario: Debug enabled
- **WHEN** logging is set to DEBUG and emails are loaded
- **THEN** log records contain each email's headers and bodies and its parse outcome

#### Scenario: Password never logged
- **WHEN** emails are loaded at any log level, including after a failed login
- **THEN** no log record contains the app password

#### Scenario: Default verbosity
- **WHEN** logging is set to INFO
- **THEN** email bodies are not logged and the numbers of fetched, parsed and failed messages are logged
