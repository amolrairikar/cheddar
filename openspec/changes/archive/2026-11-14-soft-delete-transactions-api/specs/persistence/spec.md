## ADDED Requirements

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
