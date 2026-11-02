"""Load emails from an IMAP mailbox and parse them."""

from __future__ import annotations

from .config import ImapConfig, LoaderConfigError, LoaderError
from .imap import ImapLoader, LoadedEmail, message_to_email
from .pipeline import FailedEntry, LoadResult, ParsedEntry, load_and_parse

__all__ = ["FailedEntry", "ImapConfig", "ImapLoader", "LoadResult",
           "LoadedEmail", "LoaderConfigError", "LoaderError", "ParsedEntry",
           "load_and_parse", "message_to_email"]
