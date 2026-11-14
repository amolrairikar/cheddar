## Purpose

Stores parsed transactions and investment positions in a local SQLite database so they survive beyond a single refresh and can be categorized, tagged and queried later.

## Requirements

### Requirement: Database location and creation
The system SHALL store data in the SQLite database file named by the environment variable `CHEDDAR_DB_PATH`, defaulting to `./cheddar.db`. If the file or its tables do not exist, the system SHALL create them automatically. Opening an existing database SHALL NOT remove or alter data already stored.

#### Scenario: Default location
- **WHEN** `CHEDDAR_DB_PATH` is not set
- **THEN** the database is `./cheddar.db`

#### Scenario: Custom location
- **WHEN** `CHEDDAR_DB_PATH` is set to `/data/money.db`
- **THEN** the database is `/data/money.db`

#### Scenario: First use creates tables
- **WHEN** the database file does not exist and data is saved
- **THEN** the file and the transaction, tag and investment position tables are created

#### Scenario: Existing data preserved
- **WHEN** the database already holds transactions and is opened again
- **THEN** the existing rows are unchanged

### Requirement: Transaction storage
The system SHALL store each parsed transaction as one row with an original merchant (from `merchant`), original amount (from `amount`), account, transaction timestamp (from `timestamp`), and the source email ID, which is the Message-ID of the email the transaction was parsed from (or the email's IMAP UID when the email has no Message-ID). The amount SHALL be stored without loss of precision. The source email ID SHALL be required and unique across transactions: saving a transaction whose source email ID is already stored SHALL leave the stored row unchanged and SHALL NOT raise an error or add a row. Each stored transaction SHALL also have an empty category and an empty transaction type. When set, the transaction type SHALL be either `Income` or `Expense`; the database SHALL reject any other value.

#### Scenario: Transaction saved with mapped fields
- **WHEN** a transaction with merchant `Trader Joe's`, amount `-23.45`, account `Chase 1234` and timestamp `2026-10-29T22:01:51+00:00` is saved
- **THEN** one row holds original merchant `Trader Joe's`, original amount `-23.45`, account `Chase 1234` and transaction timestamp `2026-10-29T22:01:51+00:00`

#### Scenario: Source email ID stored
- **WHEN** a transaction parsed from the email with Message-ID `<abc@mail.example.com>` is saved
- **THEN** its row holds the source email ID `<abc@mail.example.com>`

#### Scenario: Same email saved again
- **WHEN** a transaction from the email with Message-ID `<abc@mail.example.com>` is saved, and another transaction with different values from the same email is saved afterwards
- **THEN** one row exists for that source email ID, it holds the first transaction's values, and no error is raised

#### Scenario: Different emails with identical details
- **WHEN** two transactions with the same merchant, amount, account and timestamp come from two emails with different Message-IDs
- **THEN** both are stored as separate rows

#### Scenario: Missing source email ID rejected
- **WHEN** a transaction is saved without a source email ID
- **THEN** the database rejects it

#### Scenario: Category and type start empty
- **WHEN** a transaction is saved
- **THEN** its category and transaction type are empty

#### Scenario: Amount precision preserved
- **WHEN** a transaction with amount `0.10` is saved and read back
- **THEN** the amount is exactly `0.10`

#### Scenario: Invalid transaction type rejected
- **WHEN** a transaction's type is set to a value other than `Income` or `Expense`
- **THEN** the database rejects the change

#### Scenario: Valid transaction type accepted
- **WHEN** a transaction's type is set to `Income`
- **THEN** the change is stored

### Requirement: Transaction tags
The system SHALL allow a stored transaction to have any number of tags, each a text value. A transaction SHALL NOT have the same tag twice. A newly saved transaction SHALL have no tags. Deleting a transaction SHALL delete its tags.

#### Scenario: New transaction has no tags
- **WHEN** a transaction is saved
- **THEN** it has no tags

#### Scenario: Multiple tags
- **WHEN** the tags `vacation` and `shared` are added to one transaction
- **THEN** the transaction has both tags

#### Scenario: Duplicate tag rejected
- **WHEN** the tag `vacation` is added twice to the same transaction
- **THEN** the database rejects the second addition

#### Scenario: Tags removed with transaction
- **WHEN** a transaction with tags is deleted
- **THEN** its tags are deleted too

### Requirement: Investment position storage
The system SHALL store each position of a parsed position summary as one row holding its ticker, quantity, price, value, account, account type and snapshot date, as given. Quantity, price and value SHALL be stored without loss of precision. A position SHALL be identified by its account, ticker and snapshot date: saving a position that matches a stored one SHALL replace the stored values rather than add a row. The summary's account balance SHALL NOT be stored.

#### Scenario: Positions saved
- **WHEN** a position summary with two positions is saved
- **THEN** two rows exist, each with the position's ticker, quantity, price, value, account, account type and snapshot date

#### Scenario: Re-saving the same position
- **WHEN** a position for account `Fidelity 5678`, ticker `VTI` and snapshot date `2026-10-29` is saved twice, the second time with a different price
- **THEN** one row exists for it and it holds the second price

#### Scenario: Same ticker on another date
- **WHEN** a position for the same account and ticker is saved with a different snapshot date
- **THEN** both rows exist

#### Scenario: Decimal precision preserved
- **WHEN** a position with quantity `10.5000` is saved and read back
- **THEN** the quantity is exactly `10.5000`

### Requirement: Atomic saves
The system SHALL save all results of a refresh as a single unit: either every transaction and position from that refresh is stored, or none is.

#### Scenario: Failure rolls back
- **WHEN** saving the third of three transactions fails
- **THEN** none of the three transactions is stored

### Requirement: Soft deletion of transactions
The system SHALL support marking a stored transaction as deleted without removing it. A deleted transaction SHALL record the UTC time it was deleted; an active transaction SHALL have no deletion time. Marking a transaction deleted SHALL leave all its other values, its tags and its source email ID unchanged. Marking an already deleted transaction deleted SHALL NOT change its recorded deletion time. A newly saved transaction SHALL be active.

#### Scenario: New transaction is active
- **WHEN** a transaction is saved
- **THEN** it has no deletion time

#### Scenario: Transaction soft-deleted
- **WHEN** a stored transaction with tags is marked deleted
- **THEN** its row still exists with all original values and tags, and it has a deletion time

#### Scenario: Deleting twice
- **WHEN** a deleted transaction is marked deleted again
- **THEN** its deletion time is unchanged

#### Scenario: Soft-deleted transaction not re-imported
- **WHEN** a transaction is soft-deleted and a transaction from the same source email is saved again
- **THEN** no row is added and the transaction stays deleted

### Requirement: In-place upgrade of existing databases
Opening a database created before soft deletion existed SHALL add the deletion marker to its transactions without removing or changing any stored data, and every existing transaction SHALL be active afterwards. Opening an already upgraded database SHALL change nothing.

#### Scenario: Older database upgraded
- **WHEN** a database whose transactions have no deletion marker and that holds two transactions is opened
- **THEN** both transactions are still stored with their original values and are active

#### Scenario: Upgrade is repeatable
- **WHEN** an upgraded database is opened again
- **THEN** it opens without error and its data is unchanged
