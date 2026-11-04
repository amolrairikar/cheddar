# cheddar
A local first personal finance app that uses data parsed from emails to track income, expenses, and investments

# Getting Started
## Transaction Alerts
<details>
<summary><b>American Express</b></summary>

*NOTE: This can only be done on web*

`Account Services` -> `Alerts and Communications` -> `Account Alerts` -> `Large Purchase` -> Enter $1 for the threshold and select your email for receiving the alert

</details>

<details>
<summary><b>Capital One</b></summary>

Navigate to `Profile` -> `Alerts and notifications` -> Pick the account to add alerts for -> `Instant purchase notifications` -> Set the amount to $1 and select the checkbox for email

</details>

<details>
<summary><b>Chase</b></summary>

Go to your profile -> `Alerts & messages` -> `Manage alerts` -> Pick the account to add alerts for -> `Transactions` -> `Single transaction above` --> Pick $0.01 for the minimum threshold and select the checkbox for your email

</details>

<details>
<summary><b>Fidelity</b></summary>

*NOTE: This can only be done on web*

Go to your profile icon -> `Profile` -> `Settings and more` -> `Preferences` -> `Communication Preferences` -> `Other preferences` -> `Alerts & notifications` -> `Transactions and events` -> `Balances and notices` -> `Accounts positions` -> Select all accounts, pick a time of day to receive the notification, and click the checkbox for your email

</details>

<details>
<summary><b>Venmo</b></summary>

Navigate to `Me` -> `Settings` -> `Notifications` -> `Email Notifications` -> Select the checkbox for `Payment Received` and `Purchases`

</details>

## Email Inbox Setup
1. Create 3 labels/folders in your email inbox: transactions-pending, transactions-failed, and transactions-processed

   After each refresh, emails that parsed successfully are moved to `transactions-processed` and emails that failed are moved to `transactions-failed`. These folders must exist, or the refresh returns an error. To use different folder names, set `CHEDDAR_IMAP_FOLDER` (default `transactions-pending`), `CHEDDAR_IMAP_PROCESSED_FOLDER` (default `transactions-processed`) and `CHEDDAR_IMAP_FAILED_FOLDER` (default `transactions-failed`).
2. Set up the following email filtering rules for the banks/brokerages you use:

| Institution      | From address           | Filter Criteria | Apply label          |
|------------------|------------------------|------------------|----------------------|
| American Express | AmericanExpress@welcome.americanexpress.com       | Subject contains `Large Purchase Approved`      | transactions-pending |
| Capital One      | capitalone@notification.capitalone.com | Subject contains `A new transaction was charged to your account`         | transactions-pending |
| Chase            | no.reply.alerts@chase.com      | Email body contains `You are receiving this alert because your transaction was more than the`            | transactions-pending |
| Venmo            | venmo@venmo.com        | Subject contains `paid`          | transactions-pending |
| Fidelity         | fidelity.alerts@fidelity.com   | Subject contains `Fidelity Alerts: Position Summary`     | transactions-pending |

## Data Storage
Parsed transactions and investment positions are saved to a SQLite database. By default this is `./cheddar.db`; set `CHEDDAR_DB_PATH` to use a different file. The tables are created automatically on first use. Each transaction is stored with the Message-ID of the email it came from, so processing the same email twice never creates a duplicate. Emails are moved out of `transactions-pending` only after their data has been saved, so if saving fails the emails stay in place and the next refresh retries them.

# Supported Email Apps
Any email providers that takes a username/password over IMAP. These include:
- GMail
- Yahoo/AOL
- iCloud
- Fastmail
- Zoho


# Supported Bank/Brokerage Email Formats
## Banks
- American Express
- Capital One
- Chase
- Venmo

*NOTE: Chase also supports transactions to/from a checking account

## Brokerages
- Fidelity

## Requesting a new parser
Want support for a bank or brokerage that isn't listed? [Fill out the new parser issue template](https://github.com/amolrairikar/cheddar/issues/new?template=new-parser.md) with a redacted sample of the email.
