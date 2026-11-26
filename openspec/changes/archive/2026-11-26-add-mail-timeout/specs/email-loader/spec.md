## ADDED Requirements

### Requirement: Mail connection timeout
The system SHALL limit each wait on the mail server, both while connecting and while waiting for data afterwards, to 30 seconds. This limit SHALL NOT apply to the total duration of loading or moving messages. A timeout while connecting or logging in SHALL raise a loader error that does not contain the app password.

#### Scenario: Server does not respond during connection
- **WHEN** the server does not respond within 30 seconds while the system is connecting or logging in
- **THEN** the system raises a loader error that does not contain the password

#### Scenario: Server stops responding after login
- **WHEN** the server sends nothing for 30 seconds while a folder is selected, searched or moved from
- **THEN** the system raises a loader error

## MODIFIED Requirements

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
