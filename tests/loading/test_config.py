import pytest
from email_parser.loading import ImapConfig, LoaderConfigError


def test_defaults():
    cfg = ImapConfig.from_env({"CHEDDAR_IMAP_USER": "a@b.c", "CHEDDAR_IMAP_PASSWORD": "pw"})
    assert (cfg.host, cfg.port, cfg.folder) == ("imap.gmail.com", 993, "transactions-pending")


def test_overrides():
    cfg = ImapConfig.from_env({"CHEDDAR_IMAP_USER": "a@b.c", "CHEDDAR_IMAP_PASSWORD": "pw",
                               "CHEDDAR_IMAP_FOLDER": "INBOX", "CHEDDAR_IMAP_HOST": "h"})
    assert (cfg.host, cfg.folder) == ("h", "INBOX")


def test_missing_variable_named_without_secrets():
    with pytest.raises(LoaderConfigError) as exc:
        ImapConfig.from_env({"CHEDDAR_IMAP_USER": "a@b.c"})
    assert "CHEDDAR_IMAP_PASSWORD" in str(exc.value)
    assert "a@b.c" not in str(exc.value)


def test_password_not_in_repr():
    assert "s3cret" not in repr(ImapConfig("u", "s3cret"))
