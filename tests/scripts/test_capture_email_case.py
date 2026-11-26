import tomllib

import capture_email_case as capture
import pytest
from email_parser.parsing import Email
from imap_fakes import build

VENMO = "Venmo <venmo@venmo.com>"
CAPITAL_ONE = "capitalone@notification.capitalone.com"
SENTENCE = ("About your Venture X Card ending in 1234 at {}, a purchase in the "
            "amount of $5.00 was made.")


def email(sender, subject="", plain="", html=""):
    return Email("1", sender, subject, "2026-10-15T14:30:00+00:00", plain, html)


def run(tmp_path, message, *extra):
    source = tmp_path / "raw.eml"
    source.write_bytes(bytes(message))
    return capture.main([str(source), "bank/case", "--cases-dir", str(tmp_path / "cases"), *extra])


def test_writes_only_a_draft_with_blank_expected(tmp_path, capsys):
    message = build(sender=VENMO, subject="You paid Jane Doe $5.00", plain="", html="<p>Hi</p>")
    assert run(tmp_path, message) == 0
    [draft] = (tmp_path / "cases" / "bank").iterdir()
    assert draft.name == "case.toml.draft"
    case = tomllib.loads(draft.read_text())
    assert case["sender"] == VENMO
    assert case["subject"] == "You paid Jane Doe $5.00"
    assert case["body"] == "Hi\n"
    assert case["expected"] == {"merchant": "", "amount": "", "account": ""}
    assert "warning" not in capsys.readouterr().err


@pytest.mark.parametrize("name", ["case.toml", "case.toml.draft"])
def test_refuses_to_overwrite(tmp_path, name):
    existing = tmp_path / "cases" / "bank" / name
    existing.parent.mkdir(parents=True)
    existing.write_text("keep")
    assert run(tmp_path, build()) == 1
    assert existing.read_text() == "keep"


def test_warns_when_no_body_reproduces_the_parse(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(capture, "select_body", lambda *args: ("text", False))
    assert run(tmp_path, build()) == 0
    assert "does not parse the same way" in capsys.readouterr().err


def test_html_text_selected_by_default():
    message = email("new@bank.example", plain="plain", html="<p>from html</p>")
    assert capture.select_body(message) == ("from html", True)


def test_plain_selected_when_parser_reads_it():
    message = email(CAPITAL_ONE, plain=SENTENCE.format("Plain Shop"),
                    html=f"<p>{SENTENCE.format('Html Shop')}</p>")
    assert capture.select_body(message) == (message.plain, True)


def test_plain_flag():
    message = email("new@bank.example", plain="plain", html="<p>from html</p>")
    assert capture.select_body(message, plain=True) == ("plain", True)


def test_unfaithful_body_is_flagged():
    message = email(CAPITAL_ONE, plain=SENTENCE.format("Plain Shop"))
    original = capture._outcome(message)
    outcomes = iter([original, "different", "different"])
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(capture, "_outcome", lambda _: next(outcomes))
        assert capture.select_body(message)[1] is False


@pytest.mark.parametrize("body", [
    'quotes """ and """" and \\ backslash',
    'ends with a quote "',
    "tab\there\r\nwindows\x00\x7f newline",
])
def test_draft_is_valid_toml(body):
    draft = capture.render_draft(email('"A" <a@b.com>', 'say "hi" \\ \x7f'), body)
    case = tomllib.loads(draft)
    assert case["sender"] == '"A" <a@b.com>'
    assert case["subject"] == 'say "hi" \\ '
    assert case["body"] == body.replace("\r\n", "\n").replace("\x00", "").replace("\x7f", "") + "\n"


def test_empty_body_is_omitted():
    assert "body" not in tomllib.loads(capture.render_draft(email(VENMO), "  \n"))
