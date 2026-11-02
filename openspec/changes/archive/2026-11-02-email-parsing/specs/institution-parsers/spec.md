## Purpose

Specifies which email shapes from Chase, American Express, Capital One, Venmo, and Fidelity are supported and the data extracted from each.

## ADDED Requirements

### Requirement: Chase emails
The system SHALL parse Chase emails from the sender: direct-deposit alerts (subject) as positive transactions with merchant "direct deposit"; sent-money alerts (subject) as negative transactions with a blank merchant; and card transaction alerts (body fields Account, Merchant, Amount) as negative transactions. The account label SHALL include the last four digits, with "Chase Checking" for subject-based alerts and the card name for card alerts.

#### Scenario: Direct deposit
- **WHEN** a Chase email has subject "$1,234.56 direct deposit posted to account ending in (...1234)"
- **THEN** the result is +1234.56, merchant "direct deposit", account "Chase Checking 1234"

#### Scenario: Transfer sent
- **WHEN** a Chase email has subject "You sent $50.00 from account ending in 9876"
- **THEN** the result is -50.00 on account "Chase Checking 9876"

#### Scenario: Card alert
- **WHEN** a Chase body contains "Account United Quest Visa (...1234)", "Merchant UBER *TRIP", and "Amount $17.99"
- **THEN** the result is -17.99, merchant "UBER *TRIP", account "United Quest Visa 1234"

#### Scenario: Other Chase email
- **WHEN** a Chase email matches none of these shapes
- **THEN** a parse error is raised

### Requirement: American Express emails
The system SHALL parse American Express large-purchase alerts from the HTML body as negative transactions on account "American Express <digits>", using the "Account Ending" number and taking the merchant from the line preceding the amount marked with a trailing asterisk, ignoring unmarked amounts such as the alert threshold.

#### Scenario: Purchase alert
- **WHEN** the body has "Account Ending: 12345", a threshold amount "$1.00", merchant "UNITED ELEC TICKETNG", and "$8.00*"
- **THEN** the result is -8.00, merchant "UNITED ELEC TICKETNG", account "American Express 12345"

### Requirement: Capital One emails
The system SHALL parse Capital One purchase and pending-authorization alerts from the plain-text body as negative transactions, taking the card name and last four digits from "About your <card> Card ending in NNNN" and the merchant and amount from the purchase sentence, tolerating line wrapping and thousands separators.

#### Scenario: Wrapped purchase sentence
- **WHEN** the merchant name wraps across lines in a purchase of $1,200.50 on a Venture X card ending 4950
- **THEN** the result is -1200.50, merchant with whitespace normalized, account "Venture X 4950"

### Requirement: Venmo emails
The system SHALL parse Venmo emails from the subject: "You paid <name> $N" as a negative transaction and "<name> paid $N to your Venmo account" or "<name> paid your $N request" as a positive transaction, on account "Venmo" with the counterparty as merchant and the email date as timestamp.

#### Scenario: Payment sent
- **WHEN** the subject is "You paid Jane Doe $12.00"
- **THEN** the result is -12.00, merchant "Jane Doe", account "Venmo"

#### Scenario: Payment received
- **WHEN** the subject is "Jane Doe paid $5.25 to your Venmo account"
- **THEN** the result is +5.25, merchant "Jane Doe", account "Venmo"

#### Scenario: Payment received for a request
- **WHEN** the subject is "Jane Doe paid your $48.50 request"
- **THEN** the result is +48.50, merchant "Jane Doe", account "Venmo"

### Requirement: Fidelity position summaries
The system SHALL parse Fidelity position summary emails into a position summary for account "Fidelity <last four>", reading each row of the positions table (symbol, account type, quantity, price, value) and the stated total as the balance. It SHALL raise a parse error if the table is malformed or the position values do not sum to the total within one cent.

#### Scenario: Valid summary
- **WHEN** a table lists VTI ($2,000.00) and FXAIX ($550.00) with a Total of $2,550.00
- **THEN** the result has balance 2550.00 and two positions in order

#### Scenario: Total mismatch
- **WHEN** the listed values do not sum to the stated total
- **THEN** a parse error is raised
