"""Turn a raw .eml file into a draft parser test case.

    uv run python scripts/capture_email_case.py path/to/email.eml chase/card_alert

writes tests/parsing/cases/chase/card_alert.toml.draft, which git ignores.
Redact it, fill in [expected], then rename it to .toml. Nothing is redacted
automatically. Runs locally and makes no network calls.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from email import message_from_binary_file, policy
from pathlib import Path

from email_parser.loading import message_to_email
from email_parser.parsing import Email, ParseError, parse_email
from email_parser.parsing.text import email_text

CASES = Path(__file__).resolve().parent.parent / "tests" / "parsing" / "cases"

HEADER = """\
# DRAFT: before renaming this file to .toml
#   1. Redact personal data in sender, subject and body: names, email addresses,
#      account digits, amounts, balances, merchants, locations, dates and links.
#      Keep the wording and line layout unchanged.
#   2. Fill in [expected] from what the email says, not from parser output.
"""

EXPECTED = """\
[expected]
# For a transaction (negative amount = money spent):
merchant = ""
amount = ""
account = ""
# For a position summary, replace the three lines above with:
# account = ""
# balance = ""
# positions = [
#   { ticker = "", account_type = "", quantity = "", price = "", value = "" },
# ]
"""


def _outcome(email: Email):
    try:
        return parse_email(email)
    except ParseError as error:
        return str(error)


def select_body(email: Email, plain: bool = False) -> tuple[str, bool]:
    """Pick the body text a case should hold.

    Cases supply their body as plain text. Most parsers read the text extracted
    from the HTML, but some read the plain part directly, so choose whichever
    parses the same way as the original. The flag is False if neither does.
    """
    if plain:
        candidates = [email.plain]
    else:
        candidates = [email_text(email), email.plain]
    original = _outcome(email)
    for body in candidates:
        if _outcome(replace(email, plain=body, html="")) == original:
            return body, True
    return candidates[0], False


def _string(value: str) -> str:
    return json.dumps(value.replace("\x7f", ""), ensure_ascii=False)


def _multiline(value: str) -> str:
    lines = value.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(c for c in lines if c in "\n\t" or (c >= " " and c != "\x7f"))
    escaped = text.replace("\\", "\\\\").replace('"""', '""\\"')
    return f'"""\n{escaped.rstrip()}\n"""'


def render_draft(email: Email, body: str) -> str:
    fields = [f"sender = {_string(email.sender)}",
              f"subject = {_string(email.subject)}",
              f"date = {_string(email.date)}"]
    if body.strip():
        fields.append(f"body = {_multiline(body)}")
    return HEADER + "\n" + "\n".join(fields) + "\n\n" + EXPECTED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("eml", type=Path, help="raw email saved as .eml")
    parser.add_argument("name", help="case name as <institution>/<case>")
    parser.add_argument("--plain", action="store_true",
                        help="capture the plain-text part, for a new parser that reads it")
    parser.add_argument("--cases-dir", type=Path, default=CASES, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    target = args.cases_dir / f"{args.name}.toml"
    draft = target.with_name(target.name + ".draft")
    for path in (target, draft):
        if path.exists():
            print(f"error: {path} already exists", file=sys.stderr)
            return 1

    with open(args.eml, "rb") as f:
        message = message_from_binary_file(f, policy=policy.default)
    email = message_to_email(message, uid="capture")
    body, faithful = select_body(email, args.plain)

    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text(render_draft(email, body), encoding="utf-8")
    print(f"wrote {draft}")
    print("Redact it, fill in [expected], then remove the .draft suffix.")
    if not faithful:
        print("warning: the captured body does not parse the same way as the original email",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
