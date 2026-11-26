## ADDED Requirements

### Requirement: Mail connection failures during a refresh
The system SHALL respond with HTTP 502 when a mail protocol error or network error occurs after login while selecting a folder, searching or moving emails, and SHALL NOT include mail credentials in the response body. When the error occurs before results are saved, nothing from the refresh SHALL be stored and no email SHALL be moved. When it occurs while moving emails, the saved results SHALL be kept. Such an error raised while fetching an email SHALL NOT by itself fail the refresh: that email SHALL be treated as failed and the others SHALL be processed. If the connection is lost during fetching, the system SHALL save the emails already parsed, respond 502 when it cannot move emails, and move none.

#### Scenario: One fetch raises an error
- **WHEN** fetching one of several parsable emails raises an error and the connection still works
- **THEN** the system responds 200, that email is listed in `failed` and moved to the failed folder, and the others are saved and moved to the processed folder

#### Scenario: Connection lost while fetching
- **WHEN** the connection drops during fetching after at least one email has been fetched and parsed
- **THEN** the system responds 502, the parsed results are saved and no email is moved

#### Scenario: Connection lost before any email is fetched
- **WHEN** the connection drops while the first email is fetched
- **THEN** the system responds 502, nothing is added to the database and no email is moved

#### Scenario: Connection lost while moving
- **WHEN** the connection drops while a refresh is moving emails after saving its results
- **THEN** the system responds 502 and the saved results remain in the database

#### Scenario: Refresh after a connection failure
- **WHEN** a refresh has failed because the connection dropped and a new refresh is requested after the connection recovers
- **THEN** the new refresh runs normally, processes the emails still pending and stores no duplicate transaction
