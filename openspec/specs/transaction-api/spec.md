## Purpose

Lets a client list stored transactions and delete them reversibly by id, so mistaken or unwanted transactions can be removed without losing data.

## Requirements

### Requirement: List transactions endpoint
The system SHALL provide a `GET /transactions` endpoint that responds 200 with a JSON body containing a `transactions` list. By default the list SHALL contain only active (not deleted) transactions. When the query parameter `deleted=true` is given, the list SHALL contain only soft-deleted transactions instead. Each item SHALL contain the transaction `id`, `original_merchant`, `original_amount`, `account`, `transaction_timestamp`, `category`, `transaction_type`, `tags` and `deleted_at` (empty for an active transaction). Items SHALL be ordered by `id`. The endpoint SHALL NOT require authentication.

#### Scenario: Active transactions listed
- **WHEN** the database holds two active transactions and one deleted transaction and a client sends `GET /transactions`
- **THEN** the system responds 200 and `transactions` holds only the two active ones, each with its `id`

#### Scenario: Deleted transactions listed
- **WHEN** the database holds one deleted transaction and a client sends `GET /transactions?deleted=true`
- **THEN** the system responds 200 and `transactions` holds only that transaction, with a non-empty `deleted_at`

#### Scenario: Tags included
- **WHEN** an active transaction has the tags `vacation` and `shared`
- **THEN** its list item shows both tags

#### Scenario: Empty database
- **WHEN** no transactions are stored and a client sends `GET /transactions`
- **THEN** the system responds 200 with an empty `transactions` list

### Requirement: Delete transactions endpoint
The system SHALL provide a `DELETE /transactions` endpoint that accepts a JSON body `{"ids": [<integer>, ...]}` and soft-deletes each listed transaction that exists and is active. It SHALL respond 200 with a JSON body containing `deleted`, the ids that were deleted, and `not_found`, the requested ids that were not deleted because no such transaction exists or it was already deleted. A soft-deleted transaction SHALL remain stored and SHALL no longer appear in the default transaction list. An id that appears more than once in the request SHALL be reported once. An empty `ids` list SHALL succeed with both result lists empty. The endpoint SHALL NOT require authentication, and SHALL NOT wait for or be blocked by a refresh in progress.

#### Scenario: Transactions deleted
- **WHEN** transactions 1 and 2 are active and a client sends `DELETE /transactions` with `{"ids": [1, 2]}`
- **THEN** the system responds 200 with `deleted` `[1, 2]` and `not_found` `[]`, and neither appears in `GET /transactions`

#### Scenario: Some ids not found
- **WHEN** transaction 1 is active, no transaction 9999 exists, and a client sends `{"ids": [1, 9999]}`
- **THEN** the system responds 200 with `deleted` `[1]` and `not_found` `[9999]`

#### Scenario: Already deleted id
- **WHEN** transaction 1 is already deleted and a client sends `{"ids": [1]}`
- **THEN** the system responds 200 with `deleted` `[]` and `not_found` `[1]`, and the transaction's deletion time is unchanged

#### Scenario: Duplicate ids in request
- **WHEN** a client sends `{"ids": [1, 1]}` and transaction 1 is active
- **THEN** the system responds 200 with `deleted` `[1]` and `not_found` `[]`

#### Scenario: Empty id list
- **WHEN** a client sends `{"ids": []}`
- **THEN** the system responds 200 with `deleted` `[]` and `not_found` `[]`

#### Scenario: Deleted data kept
- **WHEN** a transaction is deleted
- **THEN** it still appears in `GET /transactions?deleted=true` with its original values and tags

#### Scenario: Delete during a refresh
- **WHEN** a refresh is in progress and a client sends `DELETE /transactions`
- **THEN** the system does not respond 409 and processes the delete

### Requirement: Transaction endpoint errors
The system SHALL respond 422 to `DELETE /transactions` when the body is missing, is not valid JSON, lacks `ids`, or holds an `ids` value that is not a list of integers, and SHALL NOT change any transaction. The system SHALL respond 500 with a `detail` message when the database cannot be read or written by either transaction endpoint, and a failed delete SHALL NOT change any transaction.

#### Scenario: Invalid body
- **WHEN** a client sends `DELETE /transactions` with `{"ids": ["a"]}`
- **THEN** the system responds 422 and no transaction is changed

#### Scenario: Missing ids
- **WHEN** a client sends `DELETE /transactions` with `{}`
- **THEN** the system responds 422

#### Scenario: Database failure on list
- **WHEN** the database cannot be opened and a client sends `GET /transactions`
- **THEN** the system responds 500 with a `detail` message

#### Scenario: Database failure on delete
- **WHEN** the database fails while deleting
- **THEN** the system responds 500 with a `detail` message and no transaction is marked deleted
