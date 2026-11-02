"""Read-only IMAP fetching and conversion to the parsing ``Email`` model."""

from __future__ import annotations

import imaplib
import logging
from dataclasses import dataclass
from datetime import UTC
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from typing import Self

from email_parser.parsing import Email

from .config import ImapConfig, LoaderError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadedEmail:
    uid: str
    email: Email


def _body(msg: EmailMessage, kind: str) -> str:
    part = msg.get_body((kind,))
    if part is None:
        return ""
    try:
        return part.get_content()
    except (LookupError, ValueError):
        payload = part.get_payload(decode=True) or b""
        return payload.decode("utf-8", errors="replace")


def _utc_iso(value: str | None) -> str:
    if not value:
        raise ValueError("missing Date header")
    dt = parsedate_to_datetime(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def message_to_email(msg: EmailMessage, uid: str) -> Email:
    """Convert a parsed message to ``Email``; ``uid`` is the Message-ID fallback."""
    return Email(
        message_id=str(msg["Message-ID"] or "").strip() or uid,
        sender=str(msg["From"] or ""),
        subject=str(msg["Subject"] or ""),
        date=_utc_iso(str(msg["Date"]) if msg["Date"] else None),
        plain=_body(msg, "plain"),
        html=_body(msg, "html"),
    )


class ImapLoader:
    """Context manager that fetches every message in the configured folder.

    The folder is opened read-only and bodies are fetched with BODY.PEEK, so the
    mailbox is never modified.
    """

    def __init__(self, config: ImapConfig) -> None:
        self.config = config
        self._conn: imaplib.IMAP4_SSL | None = None

    def __enter__(self) -> Self:
        cfg = self.config
        log.info("connecting to %s:%s as %s", cfg.host, cfg.port, cfg.user)
        try:
            conn = imaplib.IMAP4_SSL(cfg.host, cfg.port)
            self._conn = conn
            conn.login(cfg.user, cfg.password)
        except (imaplib.IMAP4.error, OSError) as exc:
            self._close()
            raise LoaderError(f"could not log in to {cfg.host} as {cfg.user}") from exc
        return self

    def __exit__(self, *exc_info) -> None:
        self._close()

    def _close(self) -> None:
        conn, self._conn = self._conn, None
        if conn is None:
            return
        try:
            conn.logout()
        except (imaplib.IMAP4.error, OSError):
            pass

    def fetch_emails(self) -> list[LoadedEmail]:
        """Fetch all messages; undecodable ones are skipped with a warning."""
        return [loaded for loaded, _ in self.fetch_raw() if loaded is not None]

    def fetch_raw(self) -> list[tuple[LoadedEmail | None, str]]:
        """Fetch all messages as ``(loaded_or_None, uid)`` pairs.

        ``None`` marks a message that could not be converted, so callers can
        report it as a failure instead of losing it.
        """
        if self._conn is None:
            raise LoaderError("loader is not connected; use it as a context manager")
        conn, folder = self._conn, self.config.folder
        try:
            status, _ = conn.select(f'"{folder}"', readonly=True)
        except imaplib.IMAP4.error as exc:
            raise LoaderError(f"could not select folder {folder!r}") from exc
        if status != "OK":
            raise LoaderError(f"could not select folder {folder!r}")
        status, data = conn.uid("SEARCH", None, "ALL")
        if status != "OK":
            raise LoaderError(f"search failed in folder {folder!r}")
        uids = data[0].decode().split() if data and data[0] else []
        log.info("found %d message(s) in %s", len(uids), folder)

        results: list[tuple[LoadedEmail | None, str]] = []
        for uid in uids:
            status, parts = conn.uid("FETCH", uid, "(BODY.PEEK[])")
            raw = next((p[1] for p in parts or [] if isinstance(p, tuple)), None)
            if status != "OK" or raw is None:
                log.warning("could not fetch uid %s", uid)
                results.append((None, uid))
                continue
            try:
                msg = message_from_bytes(raw, policy=policy.default)
                email = message_to_email(msg, uid)
            except Exception:
                log.warning("could not convert uid %s", uid, exc_info=True)
                results.append((None, uid))
                continue
            log.debug(
                "uid=%s message_id=%s sender=%s subject=%s date=%s\n"
                "--- plain ---\n%s\n--- html ---\n%s",
                uid, email.message_id, email.sender, email.subject, email.date,
                email.plain, email.html)
            results.append((LoadedEmail(uid, email), uid))
        return results
