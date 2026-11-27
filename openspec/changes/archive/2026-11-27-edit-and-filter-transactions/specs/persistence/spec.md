## ADDED Requirements

### Requirement: Edited merchant and amount
The system SHALL allow a stored transaction to hold an edited merchant and an edited amount separately from its original merchant and original amount. Setting or clearing an edited value SHALL NOT change the original values. A newly saved transaction SHALL have no edited values. The edited amount SHALL be stored without loss of precision. Saving another transaction from the same source email SHALL NOT change any edited value, category, transaction type or tag.

#### Scenario: New transaction is unedited
- **WHEN** a transaction is saved
- **THEN** it has no edited merchant and no edited amount

#### Scenario: Originals preserved
- **WHEN** a transaction's merchant and amount are edited
- **THEN** its original merchant and original amount are unchanged

#### Scenario: Edits survive re-import
- **WHEN** a transaction is edited and a transaction from the same source email is saved again
- **THEN** no row is added and the edited values, category, transaction type and tags are unchanged

## MODIFIED Requirements

### Requirement: In-place upgrade of existing databases
Opening a database created before soft deletion or before merchant and amount editing existed SHALL add whatever the transactions are missing (the deletion marker, the edited merchant and the edited amount) without removing or changing any stored data. Transactions that had no deletion marker SHALL be active afterwards, existing deletion times SHALL be kept, and transactions that could not previously hold edits SHALL have none. Opening an already upgraded database SHALL change nothing.

#### Scenario: Older database upgraded
- **WHEN** a database whose transactions have no deletion marker and that holds two transactions is opened
- **THEN** both transactions are still stored with their original values and are active

#### Scenario: Database without edit support upgraded
- **WHEN** a database that has deletion markers but no edited values, holding one deleted transaction, is opened
- **THEN** the transaction is still deleted with the same deletion time and has no edited values

#### Scenario: Upgrade is repeatable
- **WHEN** an upgraded database is opened again
- **THEN** it opens without error and its data is unchanged
