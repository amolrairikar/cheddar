## ADDED Requirements

### Requirement: Server and network errors after login
The system SHALL raise a loader error when a mail protocol error or a network error occurs while selecting a folder, searching or moving messages. The error message SHALL NOT contain the app password. An error raised while selecting SHALL name the folder being selected, one raised while searching SHALL name the pending folder, and one raised while moving messages after the folder is selected SHALL name the destination folder. A mail protocol error or network error raised while fetching a message SHALL NOT raise a loader error: the system SHALL record a failure for that message and continue with the next one. A fetch that the server answers with a non-OK status or without message content SHALL likewise be recorded as a failure of that message only.

#### Scenario: Connection lost during search
- **WHEN** the connection drops while the pending folder is searched
- **THEN** the system raises a loader error naming the pending folder

#### Scenario: One fetch raises an error
- **WHEN** fetching the second of three messages raises a mail protocol error or a network error and the connection still works
- **THEN** the second message is recorded as failed and the first and third are fetched

#### Scenario: Connection lost during fetch
- **WHEN** the connection drops while the second of three messages is fetched
- **THEN** the first message is fetched and the second and third are recorded as failed

#### Scenario: Network error while selecting
- **WHEN** a network error occurs while a folder is selected
- **THEN** the system raises a loader error naming that folder

#### Scenario: Network error while moving
- **WHEN** a network error occurs while messages are copied, flagged or expunged during a move
- **THEN** the system raises a loader error naming the destination folder

#### Scenario: Server rejects one fetch
- **WHEN** the server answers the fetch of one message with a non-OK status
- **THEN** that message is recorded as failed and the remaining messages are fetched
