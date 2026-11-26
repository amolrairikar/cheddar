---
name: Request a new bank/brokerage
about: Ask for email parsing support for an institution that isn't supported yet
title: "Add parser for <institution name>"
labels: new-institution
---

## Institution
<!-- e.g. Wells Fargo, Schwab, PayPal -->

**Type:** <!-- Bank / Credit card / Payment app / Brokerage -->

## Email types
<!-- Which emails should be parsed? e.g. purchase alerts, deposits, transfers, position summaries -->

## How to enable the alert
<!-- Where in the institution's app/website do you turn these emails on? -->

## Email details
- **From address:**
- **Subject line(s):**
- **Where the data lives:** <!-- subject / plain-text body / HTML body -->

## Sample email(s)
<!--
One example per email type. Please don't attach or paste the raw email (.eml) or its HTML: they hide personal data in headers, links and tracking tokens.

Instead, save the email as .eml and run this from a clone of the repository (it runs locally):

    uv run python scripts/capture_email_case.py path/to/email.eml <institution>/<email_type>

Redact the draft it writes, then paste its contents here. If the draft has no body or is missing details you can see in the email, try again with --plain (delete the first draft or use another name).
-->

> **Nothing is redacted automatically.** Before posting, remove or replace names, email addresses, account/card numbers (keep the last 4 digits only if you like), amounts or balances you consider private, merchants, locations, addresses and links. Keep the wording and line layout exactly as captured.

## Expected result
<!-- For each sample, what should be parsed? e.g. merchant "Starbucks", amount -5.40, account "Visa 1234" -->
