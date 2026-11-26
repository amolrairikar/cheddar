"""A raw message through MIME decoding, date conversion, and parsing."""

from decimal import Decimal
from email import message_from_bytes, policy

from email_parser.loading import message_to_email
from email_parser.parsing import Transaction, parse_email

# Encoded sender name, folded subject, quoted-printable HTML, and a non-UTC date.
RAW = b"""\
Message-ID: <mime-1@example.com>
From: =?utf-8?q?American_Express?= <AmericanExpress@welcome.americanexpress.com>
Subject: Large Purchase
 Approved
Date: Mon, 26 Oct 2026 06:56:05 -0700
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="b"

--b
Content-Type: text/plain; charset=utf-8

See the HTML version.
--b
Content-Type: text/html; charset=utf-8
Content-Transfer-Encoding: quoted-printable

<table><tr><td>Account Ending: 12345</td></tr><tr><td>CAF=C3=89 EXAMP=
LE</td></tr><tr><td>$9.99*</td></tr></table>
--b--
"""


def test_raw_message_parses():
    email = message_to_email(message_from_bytes(RAW, policy=policy.default), "1")
    assert email.subject == "Large Purchase Approved"
    assert parse_email(email) == Transaction(
        "CAFÉ EXAMPLE", Decimal("-9.99"), "American Express 12345",
        "2026-10-26T13:56:05+00:00")
