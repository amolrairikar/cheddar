## Purpose

Lets a client list stored transactions and delete them reversibly by id, so mistaken or unwanted transactions can be removed without losing data.

## Requirements

### Requirement: List transactions endpoint
The system SHALL provide a `GET /transactions` endpoint that responds 200 with a JSON body containing a `transactions` list. By default the list SHALL contain only active (not deleted) transactions. When the query parameter `deleted=true` is given, the list SHALL contain only soft-deleted transactions instead. Each item SHALL contain the transaction `id`, `original_merchant`, `original_amount`, `merchant`, `amount`, `account`, `transaction_timestamp`, `category`, `transaction_type`, `tags` and `deleted_at` (empty for an active transaction). `merchant` and `amount` SHALL be the edited values when set and otherwise equal the original values. Items SHALL be ordered by `id`. The endpoint SHALL NOT require authentication.

#### Scenario: Active transactions listed
- **WHEN** the database holds two active transactions and one deleted transaction and a client sends `GET /transactions`
- **THEN** the system responds 200 and `transactions` holds only the two active ones, each with its `id`

#### Scenario: Deleted transactions listed
- **WHEN** the database holds one deleted transaction and a client sends `GET /transactions?deleted=true`
- **THEN** the system responds 200 and `transactions` holds only that transaction, with a non-empty `deleted_at`

#### Scenario: Tags included
- **WHEN** an active transaction has the tags `vacation` and `shared`
- **THEN** its list item shows both tags

#### Scenario: Unedited values
- **WHEN** a transaction has never been edited
- **THEN** its `merchant` and `amount` equal `original_merchant` and `original_amount`

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

### Requirement: Update transaction endpoint
The system SHALL provide a `PATCH /transactions/{id}` endpoint that accepts a JSON object with any of `merchant`, `amount`, `category`, `transaction_type` and `tags`, changes only the fields present, and responds 200 with the updated transaction in the same form as a list item. `merchant` SHALL be a string, which may be empty. `amount` SHALL be a finite decimal of at most 20 digits, which may be zero, and SHALL be returned as a decimal string in plain notation. `category` SHALL be a non-blank string and `transaction_type` SHALL be `Income` or `Expense`. `tags` SHALL be a list of non-blank strings that replaces all of the transaction's tags. Surrounding whitespace SHALL be removed from `category` and tags, and a repeated tag SHALL be stored once. A `null` value SHALL revert `merchant` or `amount` to the original and SHALL clear `category` or `transaction_type`. An empty object SHALL change nothing. The endpoint SHALL NOT require authentication, and SHALL NOT wait for or be blocked by a refresh in progress.

#### Scenario: Fields updated
- **WHEN** a client sends `PATCH /transactions/1` with `{"category": "Travel", "transaction_type": "Expense", "tags": ["work"]}`
- **THEN** the system responds 200 with those values, and all other fields are unchanged

#### Scenario: Merchant and amount edited
- **WHEN** a client sends `{"merchant": "Uber", "amount": "-15.00"}` for a transaction whose original merchant is `UBER *TRIP`
- **THEN** `merchant` is `Uber` and `amount` is `-15.00`, while `original_merchant` and `original_amount` are unchanged

#### Scenario: Null reverts or clears
- **WHEN** an edited and categorized transaction is patched with `{"merchant": null, "category": null}`
- **THEN** `merchant` equals `original_merchant` and `category` is `null`

#### Scenario: Tags replaced
- **WHEN** a transaction tagged `a` and `b` is patched with `{"tags": [" c ", "c"]}`
- **THEN** its only tag is `c`

#### Scenario: Tags cleared
- **WHEN** a client sends `{"tags": []}`
- **THEN** the transaction has no tags

#### Scenario: Empty object
- **WHEN** a client sends `{}` for an active transaction
- **THEN** the system responds 200 with the transaction unchanged

#### Scenario: Update during a refresh
- **WHEN** a refresh is in progress and a client sends a valid update
- **THEN** the system does not respond 409 and processes the update

### Requirement: Protected fields and update errors
The system SHALL respond 422 to an update, without changing anything, when the body is missing or is not a JSON object, when it contains any field other than those the update endpoint accepts (including `id`, `original_merchant`, `original_amount`, `transaction_timestamp`, `account` and `deleted_at`), when a value is invalid (including `null` for `tags`), or when the path id is not a positive integer that the database can hold. It SHALL respond 404 with `detail` `transaction not found` when no active transaction has the id, including when the transaction is deleted. It SHALL respond 500 with a `detail` message when the database fails, leaving the transaction unchanged.

#### Scenario: Protected field rejected
- **WHEN** a client sends `{"category": "Travel", "account": "Other"}`
- **THEN** the system responds 422 and neither field is changed

#### Scenario: Invalid value
- **WHEN** a client sends `{"transaction_type": "Transfer"}`, `{"amount": "abc"}`, `{"category": "  "}` or `{"tags": null}`
- **THEN** the system responds 422 and nothing is changed

#### Scenario: Oversized amount
- **WHEN** a client sends `{"amount": "1e999999999"}`
- **THEN** the system responds 422 and nothing is changed

#### Scenario: Unknown id
- **WHEN** a client updates id 9999 and no such transaction exists
- **THEN** the system responds 404

#### Scenario: Deleted transaction
- **WHEN** a client updates a soft-deleted transaction
- **THEN** the system responds 404 and the transaction is unchanged

#### Scenario: Database failure on update
- **WHEN** the database fails during an update
- **THEN** the system responds 500 with a `detail` message and nothing is changed

### Requirement: List transaction filters
`GET /transactions` SHALL accept the optional query parameters `start_date`, `end_date`, `merchant`, `category`, `account`, `tag` and `transaction_type`, and SHALL list only transactions that satisfy every parameter given, including the `deleted` selection. `start_date` and `end_date` are `YYYY-MM-DD` dates that bound, inclusively, the UTC date of the transaction timestamp, and either MAY be given alone. The other parameters MAY be repeated, and a transaction satisfies a repeated parameter when it matches any of its values. `merchant` SHALL match when the transaction's current merchant (edited, otherwise original) contains the value. `category`, `account` and `tag` SHALL match the whole value, and `tag` matches when any of the transaction's tags does. All text matching SHALL ignore case, including for non-ASCII letters, and SHALL treat every character literally. `transaction_type` SHALL be `Income` or `Expense`. A matching transaction SHALL be listed once, in `id` order, with all its tags.

#### Scenario: Date range is inclusive
- **WHEN** a client sends `start_date=2026-10-01&end_date=2026-10-31`
- **THEN** transactions timestamped from the start of 1 October to the end of 31 October UTC are listed and others are not

#### Scenario: Merchant substring
- **WHEN** a client sends `merchant=uber` and a transaction's merchant is `UBER *TRIP`
- **THEN** it is listed

#### Scenario: Edited merchant searched
- **WHEN** a merchant was edited from `SQ *JOES` to `Joe's Diner`
- **THEN** `merchant=diner` lists the transaction and `merchant=SQ *` does not

#### Scenario: Any of several tags
- **WHEN** a client sends `tag=work&tag=shared`
- **THEN** transactions with either tag are listed once each, showing all their tags

#### Scenario: Different filters combined
- **WHEN** a client sends `category=travel&transaction_type=Expense`
- **THEN** only transactions matching both are listed

#### Scenario: Wildcard characters are literal
- **WHEN** a client sends `merchant=%`
- **THEN** only transactions whose merchant contains `%` are listed

#### Scenario: Filters with deleted
- **WHEN** a client sends `deleted=true&account=Venmo`
- **THEN** only soft-deleted transactions for account `Venmo` are listed

#### Scenario: Nothing matches
- **WHEN** no transaction matches the filters
- **THEN** the system responds 200 with an empty `transactions` list

### Requirement: Invalid list filters
The system SHALL respond 422 to `GET /transactions` when a date is not a valid `YYYY-MM-DD` date, when a text filter value is empty or only whitespace, or when `transaction_type` is not `Income` or `Expense`. When `start_date` is after `end_date`, it SHALL respond 422 with `detail` `start_date must not be after end_date`.

#### Scenario: Invalid value
- **WHEN** a client sends `start_date=yesterday`, `transaction_type=Transfer` or `merchant=`
- **THEN** the system responds 422

#### Scenario: Reversed range
- **WHEN** a client sends `start_date=2026-11-02&end_date=2026-11-01`
- **THEN** the system responds 422 with `detail` `start_date must not be after end_date`
