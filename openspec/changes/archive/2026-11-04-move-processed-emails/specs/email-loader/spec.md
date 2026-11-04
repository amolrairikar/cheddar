## MODIFIED Requirements

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

## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Read-only mailbox access
**Reason**: The loader now relocates handled messages out of the pending folder, so the mailbox is no longer guaranteed unchanged after a refresh. The fetch step itself remains non-destructive.
**Migration**: Use "Non-destructive fetch" for fetching behavior (read-only open, no seen flag, authentication and folder errors) and "Move handled messages" for relocating messages.
