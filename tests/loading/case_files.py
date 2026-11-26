"""Read the parser test cases in tests/parsing/cases."""

import tomllib
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

from email_parser.parsing import Email

CASES = Path(__file__).resolve().parent.parent / "parsing" / "cases"


def read_case(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def case_email(case):
    # The body goes in as plain text; parsers that prefer HTML fall back to it.
    return Email("case", case["sender"], case["subject"], case["date"],
                 plain=case.get("body", ""))


def case_eml(name):
    """Raw message bytes for a case, for tests that go through the mailbox."""
    case = read_case(CASES / f"{name}.toml")
    msg = EmailMessage()
    msg["Message-ID"] = f"<{name.replace('/', '-')}@example.com>"
    msg["From"] = case["sender"]
    msg["Subject"] = case["subject"]
    msg["Date"] = format_datetime(datetime.fromisoformat(case["date"]))
    msg.set_content(case.get("body", ""))
    return msg.as_bytes()
