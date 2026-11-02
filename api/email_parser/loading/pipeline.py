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


@dataclass(frozen=True)
class FailedEntry:
    uid: str
    reason: str


@dataclass
class LoadResult:
    parsed: list[ParsedEntry] = field(default_factory=list)
    failed: list[FailedEntry] = field(default_factory=list)


def load_and_parse(loader: ImapLoader) -> LoadResult:
    """Fetch every message and parse it; per-message failures are recorded."""
    result = LoadResult()
    for loaded, uid in loader.fetch_raw():
        if loaded is None:
            result.failed.append(FailedEntry(uid, "message could not be fetched or decoded"))
            log.debug("uid=%s failed: could not be fetched or decoded", uid)
            continue
        try:
            parsed = parse_email(loaded.email)
        except ParseError as exc:
            result.failed.append(FailedEntry(uid, str(exc)))
            log.debug("uid=%s failed: %s", uid, exc)
        else:
            result.parsed.append(ParsedEntry(uid, parsed))
            log.debug("uid=%s parsed: %r", uid, parsed)
    log.info("loaded %d message(s): %d parsed, %d failed",
             len(result.parsed) + len(result.failed),
             len(result.parsed), len(result.failed))
    return result
