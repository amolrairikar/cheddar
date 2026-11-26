## MODIFIED Requirements

### Requirement: Refresh endpoint
The system SHALL provide a `POST /refresh` endpoint that loads emails from the configured pending folder, parses them, saves the parsed results to the database, moves each downloaded email out of the pending folder, and responds 200 with a JSON body containing `parsed_count`, `failed_count`, `parsed` and `failed`. Each `parsed` item SHALL contain the email `uid` and its parsed `result`, which is either a transaction or an investment position summary, distinguished by a `type` field. Each `failed` item SHALL contain the email `uid` and a `reason`. Parsed transactions and the positions of parsed position summaries SHALL be saved before any email is moved. Every successfully parsed email SHALL be moved to the processed folder, and every email that was downloaded but failed to be decoded or parsed SHALL be moved to the failed folder. An email that could not be downloaded SHALL be listed in `failed` and counted in `failed_count`, and SHALL stay in the pending folder so that a later refresh tries it again. The endpoint SHALL NOT require authentication. The system SHALL NOT provide a `POST /refresh_transactions` endpoint.

#### Scenario: Emails parsed successfully
- **WHEN** a client sends `POST /refresh` and the mailbox holds emails that parse into a transaction and a position summary
- **THEN** the system responds 200, `parsed_count` is 2, `failed_count` is 0, and `parsed` lists each `uid` with its `result`

#### Scenario: Some emails fail to parse
- **WHEN** a client sends `POST /refresh` and one email cannot be fetched, decoded or parsed
- **THEN** the system responds 200, that email appears in `failed` with its `uid` and a `reason`, and `failed_count` counts it

#### Scenario: Empty mailbox
- **WHEN** a client sends `POST /refresh` and the mailbox folder has no emails
- **THEN** the system responds 200 with counts of 0 and empty `parsed` and `failed` lists

#### Scenario: Mailbox is not modified
- **WHEN** a refresh finds no emails in the pending folder
- **THEN** no email is moved, flagged or deleted in the mailbox

#### Scenario: Parsed emails moved to processed folder
- **WHEN** a refresh parses emails successfully
- **THEN** those emails are in the processed folder and no longer in the pending folder

#### Scenario: Failed emails moved to failed folder
- **WHEN** a refresh has downloaded emails that fail to be decoded or parsed
- **THEN** those emails are in the failed folder and no longer in the pending folder

#### Scenario: Email that cannot be downloaded stays pending
- **WHEN** a refresh cannot download an email
- **THEN** the system responds 200, lists that email in `failed`, and leaves it in the pending folder and out of the failed folder

#### Scenario: Later refresh retries a download
- **WHEN** an email could not be downloaded in one refresh and can be downloaded and parsed in the next
- **THEN** the next refresh saves its result and moves it to the processed folder

#### Scenario: Second refresh does not reprocess
- **WHEN** a refresh that downloaded every email completes and a client sends `POST /refresh` again with no new mail
- **THEN** the second response has counts of 0 and empty `parsed` and `failed` lists

#### Scenario: Results saved to the database
- **WHEN** a refresh parses one transaction and one position summary with two positions
- **THEN** the database holds one transaction and two investment positions

#### Scenario: Transactions record their source email
- **WHEN** a refresh parses a transaction from an email
- **THEN** the stored transaction records that email's Message-ID as its source email ID

#### Scenario: Failed emails are not saved
- **WHEN** a refresh has only emails that fail to parse
- **THEN** nothing is added to the database

#### Scenario: Old path removed
- **WHEN** a client sends `POST /refresh_transactions`
- **THEN** the system responds 404 and does not contact the mail server

### Requirement: Mail connection failures during a refresh
The system SHALL respond with HTTP 502 when a mail protocol error or network error, including a timeout, occurs after login while selecting a folder, searching or moving emails, and SHALL NOT include mail credentials in the response body. When the error occurs before results are saved, nothing from the refresh SHALL be stored and no email SHALL be moved. When it occurs while moving emails, the saved results SHALL be kept. An error while fetching an email, whether or not it breaks the connection, SHALL NOT by itself fail the refresh: that email SHALL be reported as failed and left in the pending folder, and the others SHALL be processed. When the fetch is stopped because the system cannot reconnect, the mailbox's message identifiers are no longer valid, or 3 consecutive emails break the connection, the system SHALL respond 502, store nothing and move no email.

#### Scenario: One fetch raises an error
- **WHEN** fetching one of several parsable emails raises an error and the connection still works
- **THEN** the system responds 200, that email is listed in `failed` and stays in the pending folder, and the others are saved and moved to the processed folder

#### Scenario: Connection lost while fetching
- **WHEN** fetching one of several parsable emails times out or drops the connection and a new connection can be established
- **THEN** the system responds 200, that email is listed in `failed` and stays in the pending folder, and the others are saved and moved to the processed folder

#### Scenario: Connection lost before any email is fetched
- **WHEN** the connection drops while the first email is fetched and a new connection cannot be established
- **THEN** the system responds 502, nothing is added to the database and no email is moved

#### Scenario: Reconnect fails after emails were parsed
- **WHEN** a fetch drops the connection after other emails were parsed and a new connection cannot be established
- **THEN** the system responds 502, nothing is added to the database and no email is moved

#### Scenario: Repeated broken connections
- **WHEN** 3 consecutive emails break the connection during a refresh
- **THEN** the system responds 502, nothing is added to the database and no email is moved

#### Scenario: Connection lost while moving
- **WHEN** the connection drops while a refresh is moving emails after saving its results
- **THEN** the system responds 502 and the saved results remain in the database

#### Scenario: Refresh after a connection failure
- **WHEN** a refresh has failed because of a connection failure or timeout and a new refresh is requested after the server recovers
- **THEN** the new refresh runs normally and does not receive 409, processes the emails still pending and stores no duplicate transaction
