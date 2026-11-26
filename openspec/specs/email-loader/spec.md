## Purpose

Defines how Cheddar loads emails from an IMAP mailbox using an email address and app password, converts them to the parsing layer's email model, and runs them through the parsers.

## Requirements

### Requirement: Configuration from environment
The system SHALL read the IMAP user and app password from the environment variables `CHEDDAR_IMAP_USER` and `CHEDDAR_IMAP_PASSWORD`, and SHALL allow overriding the host, the pending folder, the processed folder and the failed folder via `CHEDDAR_IMAP_HOST`, `CHEDDAR_IMAP_FOLDER`, `CHEDDAR_IMAP_PROCESSED_FOLDER` and `CHEDDAR_IMAP_FAILED_FOLDER`. The defaults SHALL be host `imap.gmail.com` (TLS, port 993), pending folder `transactions-pending`, processed folder `transactions-processed` and failed folder `transactions-failed`. Explicit values supplied by the caller SHALL be usable instead of the environment.

#### Scenario: Required variables present
- **WHEN** `CHEDDAR_IMAP_USER` and `CHEDDAR_IMAP_PASSWORD` are set and the optional variables are not
- **THEN** the configuration uses host `imap.gmail.com`, port 993, folder `transactions-pending`, processed folder `transactions-processed` and failed folder `transactions-failed`

#### Scenario: Optional overrides
- **WHEN** `CHEDDAR_IMAP_FOLDER` is set to `INBOX`
- **THEN** the configuration uses folder `INBOX`

#### Scenario: Destination folder overrides
- **WHEN** `CHEDDAR_IMAP_PROCESSED_FOLDER` is set to `done` and `CHEDDAR_IMAP_FAILED_FOLDER` is set to `broken`
- **THEN** the configuration uses processed folder `done` and failed folder `broken`

#### Scenario: Missing required variable
- **WHEN** `CHEDDAR_IMAP_PASSWORD` is not set
- **THEN** loading the configuration fails with a configuration error that names the missing variable and does not include any credential value

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
The system SHALL pass each loaded email through the existing parsers and return, for every message, its IMAP UID together with either the parsed result or a failure reason. Each failure SHALL indicate whether the message was downloaded, and its reason SHALL say whether the message could not be downloaded, could not be decoded, or could not be parsed. A message that cannot be downloaded or decoded, that no parser recognizes, or whose parser raises a parse error SHALL be recorded as failed and SHALL NOT prevent the remaining messages from being processed.

#### Scenario: Mixed batch
- **WHEN** a batch contains one parsable email, one malformed email for a known institution, and one email no parser recognizes
- **THEN** the result contains one parsed entry and two failed entries, each identified by UID

#### Scenario: Empty folder
- **WHEN** the folder contains no messages
- **THEN** the result has no parsed and no failed entries

#### Scenario: Download and decoding failures distinguished
- **WHEN** one message cannot be downloaded and another is downloaded but cannot be decoded
- **THEN** both are recorded as failed, only the second is marked as downloaded, and their reasons differ

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

### Requirement: Non-destructive fetch
The system SHALL connect over TLS, authenticate with the configured credentials, and fetch every message in the configured pending folder without changing the mailbox: fetching SHALL NOT mark messages as read, move, label, flag or delete them.

#### Scenario: Fetch leaves mailbox unchanged
- **WHEN** emails are fetched from the pending folder
- **THEN** the folder is opened read-only and message bodies are fetched without setting the seen flag

#### Scenario: Authentication failure
- **WHEN** the server rejects the credentials
- **THEN** the system raises a loader error and the message does not contain the password

#### Scenario: Folder does not exist
- **WHEN** the configured pending folder cannot be selected
- **THEN** the system raises a loader error naming the folder

### Requirement: Move handled messages
The system SHALL provide a separate step, distinct from fetching and parsing, that moves a given list of messages, identified by IMAP UID, from the pending folder to a named destination folder. After a successful move, the messages SHALL no longer be present in the pending folder and SHALL be present in the destination folder. Moving an empty list SHALL NOT change the mailbox. If the destination folder does not exist or the move is rejected by the server, the system SHALL raise a loader error naming the destination folder.

#### Scenario: Move to processed folder
- **WHEN** messages with UIDs 1 and 2 are moved to the processed folder
- **THEN** both messages are in `transactions-processed` and neither remains in `transactions-pending`

#### Scenario: Other messages untouched
- **WHEN** messages with UIDs 1 and 2 are moved and the pending folder also holds UID 3
- **THEN** UID 3 remains in the pending folder

#### Scenario: Nothing to move
- **WHEN** an empty list of UIDs is moved
- **THEN** the mailbox is unchanged

#### Scenario: Destination folder does not exist
- **WHEN** messages are moved to a folder that does not exist
- **THEN** the system raises a loader error naming that folder and the messages remain in the pending folder

### Requirement: Server and network errors after login
The system SHALL raise a loader error when a mail protocol error or a network error, including a timeout, occurs while selecting a folder, searching or moving messages. The error message SHALL NOT contain the app password. An error raised while selecting SHALL name the folder being selected, one raised while searching SHALL name the pending folder, and one raised while moving messages after the folder is selected SHALL name the destination folder.

While fetching, a mail protocol error that leaves the connection usable, or a reply with a non-OK status or without message content, SHALL be recorded as a download failure of that message only, and fetching SHALL continue on the same connection.

A timeout, network error or closed connection while fetching a message breaks the connection. The system SHALL record a download failure for that message, SHALL NOT send any further command on that connection, and SHALL open a new connection to the pending folder, without modifying the mailbox, before fetching the next message or moving messages. The system SHALL NOT fetch the failed message again in the same load. No message SHALL be given content that the server sent for another message.

The system SHALL instead stop the fetch with a loader error, returning no results, when a new connection cannot be established, when the pending folder's UIDVALIDITY differs from its value when first selected, or when 3 consecutive messages break the connection. A message that does not break the connection SHALL reset that count.

#### Scenario: Connection lost during search
- **WHEN** the connection drops while the pending folder is searched
- **THEN** the system raises a loader error naming the pending folder

#### Scenario: One fetch raises an error
- **WHEN** fetching the second of three messages raises a mail protocol error that leaves the connection usable
- **THEN** a download failure is recorded for the second message and the first and third are fetched on the same connection

#### Scenario: Connection lost during fetch
- **WHEN** the connection drops while the second of three messages is fetched and a new connection can be established
- **THEN** a download failure is recorded for the second message and the first and third are fetched

#### Scenario: Late reply after a timeout
- **WHEN** the reply for the second of three messages arrives after the fetch has timed out
- **THEN** a download failure is recorded for the second message and the third message's result holds the third message's own content

#### Scenario: Connection lost on the last message
- **WHEN** the last message breaks the connection and a new connection can be established
- **THEN** a download failure is recorded for that message and the other messages can be moved

#### Scenario: Reconnect fails
- **WHEN** a fetch breaks the connection and a new connection cannot be established
- **THEN** the system raises a loader error and returns no results

#### Scenario: Message identifiers invalidated
- **WHEN** the pending folder's UIDVALIDITY after reconnecting differs from its earlier value
- **THEN** the system raises a loader error and fetches no further messages

#### Scenario: Repeated broken connections
- **WHEN** 3 consecutive messages break the connection
- **THEN** the system raises a loader error and returns no results

#### Scenario: Separated broken connections
- **WHEN** 3 messages break the connection and other messages are fetched successfully between them
- **THEN** the fetch completes

#### Scenario: Network error while selecting
- **WHEN** a network error occurs while a folder is selected
- **THEN** the system raises a loader error naming that folder

#### Scenario: Network error while moving
- **WHEN** a network error occurs while messages are copied, flagged or expunged during a move
- **THEN** the system raises a loader error naming the destination folder

#### Scenario: Server rejects one fetch
- **WHEN** the server answers the fetch of one message with a non-OK status
- **THEN** a download failure is recorded for that message and the remaining messages are fetched

### Requirement: Mail connection timeout
The system SHALL limit each wait on the mail server, both while connecting and while waiting for data afterwards, to 30 seconds. This limit SHALL NOT apply to the total duration of loading or moving messages. A timeout while connecting or logging in SHALL raise a loader error that does not contain the app password.

#### Scenario: Server does not respond during connection
- **WHEN** the server does not respond within 30 seconds while the system is connecting or logging in
- **THEN** the system raises a loader error that does not contain the password

#### Scenario: Server stops responding after login
- **WHEN** the server sends nothing for 30 seconds while a folder is selected, searched or moved from
- **THEN** the system raises a loader error
