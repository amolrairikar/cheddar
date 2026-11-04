## Purpose

Exposes the email load/parse pipeline over HTTP so a client or scheduler can confirm the service is healthy and trigger a transaction refresh with a single call.

## Requirements

### Requirement: Health check endpoint
The system SHALL provide a `GET /health` endpoint that returns HTTP 200 with the JSON body `{"status": "ok"}`. The endpoint SHALL NOT contact the mail server.

#### Scenario: Service is running
- **WHEN** a client sends `GET /health`
- **THEN** the system responds 200 with `{"status": "ok"}`

#### Scenario: Health check does not touch the mailbox
- **WHEN** a client sends `GET /health` and mail credentials are not configured
- **THEN** the system still responds 200 with `{"status": "ok"}`

### Requirement: Refresh transactions endpoint
The system SHALL provide a `POST /refresh_transactions` endpoint that loads emails from the configured pending folder, parses them, saves the parsed results to the database, moves each email out of the pending folder, and responds 200 with a JSON body containing `parsed_count`, `failed_count`, `parsed` and `failed`. Each `parsed` item SHALL contain the email `uid` and its parsed `result`, which is either a transaction or an investment position summary, distinguished by a `type` field. Each `failed` item SHALL contain the email `uid` and a `reason`. Parsed transactions and the positions of parsed position summaries SHALL be saved before any email is moved. Every successfully parsed email SHALL be moved to the processed folder, and every failed email SHALL be moved to the failed folder. The endpoint SHALL NOT require authentication.

#### Scenario: Emails parsed successfully
- **WHEN** a client sends `POST /refresh_transactions` and the mailbox holds emails that parse into a transaction and a position summary
- **THEN** the system responds 200, `parsed_count` is 2, `failed_count` is 0, and `parsed` lists each `uid` with its `result`

#### Scenario: Some emails fail to parse
- **WHEN** a client sends `POST /refresh_transactions` and one email cannot be fetched, decoded or parsed
- **THEN** the system responds 200, that email appears in `failed` with its `uid` and a `reason`, and `failed_count` counts it

#### Scenario: Empty mailbox
- **WHEN** a client sends `POST /refresh_transactions` and the mailbox folder has no emails
- **THEN** the system responds 200 with counts of 0 and empty `parsed` and `failed` lists

#### Scenario: Mailbox is not modified
- **WHEN** a refresh finds no emails in the pending folder
- **THEN** no email is moved, flagged or deleted in the mailbox

#### Scenario: Parsed emails moved to processed folder
- **WHEN** a refresh parses emails successfully
- **THEN** those emails are in the processed folder and no longer in the pending folder

#### Scenario: Failed emails moved to failed folder
- **WHEN** a refresh has emails that fail to be fetched, decoded or parsed
- **THEN** those emails are in the failed folder and no longer in the pending folder

#### Scenario: Second refresh does not reprocess
- **WHEN** a refresh completes and a client sends `POST /refresh_transactions` again with no new mail
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

### Requirement: Refresh error responses
The system SHALL report refresh failures with distinct HTTP status codes and SHALL NOT include mail credentials in any response body. A missing or invalid mail configuration SHALL produce HTTP 500 with a message naming the missing setting. A failure to log in to, select the folder in, or search the mailbox, or to move emails to the processed or failed folder, SHALL produce HTTP 502. A failure to save results to the database SHALL produce HTTP 500; in that case nothing from the refresh SHALL be stored and no email SHALL be moved, so the emails remain in the pending folder for the next refresh.

#### Scenario: Mail configuration missing
- **WHEN** a client sends `POST /refresh_transactions` and a required mail credential setting is not configured
- **THEN** the system responds 500, the message names the missing setting, and no credential value appears in the body

#### Scenario: Mail server rejects login
- **WHEN** a client sends `POST /refresh_transactions` and the mail server rejects the login
- **THEN** the system responds 502 and the password does not appear in the body

#### Scenario: Mailbox folder cannot be selected or searched
- **WHEN** a client sends `POST /refresh_transactions` and the configured folder cannot be selected or searched
- **THEN** the system responds 502

#### Scenario: Destination folder missing
- **WHEN** a client sends `POST /refresh_transactions` and the processed or failed folder does not exist in the mailbox
- **THEN** the system responds 502 with a message naming that folder

#### Scenario: Database failure
- **WHEN** a client sends `POST /refresh_transactions` and saving to the database fails
- **THEN** the system responds 500, nothing from that refresh is stored, and every email remains in the pending folder

#### Scenario: Retry after database failure
- **WHEN** a refresh fails because of a database error and the problem is then fixed and a client sends `POST /refresh_transactions` again
- **THEN** the same emails are processed, saved and moved

#### Scenario: Retry after failed move does not duplicate
- **WHEN** a refresh saves its transactions but moving emails fails with 502, leaving the emails in the pending folder, and a client sends `POST /refresh_transactions` again
- **THEN** the second refresh responds 200, moves the emails, and the database holds exactly one transaction per email

### Requirement: Single refresh at a time
The system SHALL run at most one refresh at a time. A `POST /refresh_transactions` request received while a refresh is in progress SHALL be rejected with HTTP 409 without contacting the mail server. The system SHALL allow a new refresh once the previous one has finished, whether it succeeded or failed.

#### Scenario: Refresh already in progress
- **WHEN** a client sends `POST /refresh_transactions` while another refresh is running
- **THEN** the system responds 409 and does not open a second mailbox session

#### Scenario: Next refresh after success
- **WHEN** a refresh completes successfully and a client sends `POST /refresh_transactions` again
- **THEN** the second request runs normally and does not receive 409

#### Scenario: Next refresh after failure
- **WHEN** a refresh fails with a 500 or 502 and a client sends `POST /refresh_transactions` again
- **THEN** the second request runs normally and does not receive 409
