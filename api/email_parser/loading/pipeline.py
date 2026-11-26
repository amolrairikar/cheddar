"""Load emails over IMAP and run them through the parsers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from email_parser.parsing import ParseError, ParseResult, parse_email

from .imap import ImapLoader

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedEntry:
    uid: str
    result: ParseResult
    message_id: str  # the source email's Message-ID (its UID when the header is missing)


@dataclass(frozen=True)
class FailedEntry:
    uid: str
    reason: str
    downloaded: bool  # False: the message is still unread and worth retrying


@dataclass
class LoadResult:
    parsed: list[ParsedEntry] = field(default_factory=list)
    failed: list[FailedEntry] = field(default_factory=list)


def load_and_parse(loader: ImapLoader) -> LoadResult:
    """Fetch every message and parse it; per-message failures are recorded."""
    result = LoadResult()
    for loaded, uid, downloaded in loader.fetch_raw():
        if loaded is None:
            reason = f"message could not be {'decoded' if downloaded else 'downloaded'}"
            result.failed.append(FailedEntry(uid, reason, downloaded))
            log.debug("uid=%s failed: %s", uid, reason)
            continue
        try:
            parsed = parse_email(loaded.email)
        except ParseError as exc:
            result.failed.append(FailedEntry(uid, str(exc), downloaded))
            log.debug("uid=%s failed: %s", uid, exc)
        else:
            result.parsed.append(ParsedEntry(uid, parsed, loaded.email.message_id))
            log.debug("uid=%s parsed: %r", uid, parsed)
    log.info("loaded %d message(s): %d parsed, %d failed",
             len(result.parsed) + len(result.failed),
             len(result.parsed), len(result.failed))
    return result
