"""IMAP connection settings, read from the environment."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_HOST = "imap.gmail.com"
DEFAULT_PORT = 993
DEFAULT_FOLDER = "transactions-pending"


class LoaderError(Exception):
    """Fetching mail from the IMAP server failed."""


class LoaderConfigError(LoaderError):
    """The loader configuration is incomplete."""


@dataclass(frozen=True)
class ImapConfig:
    user: str
    password: str = field(repr=False)
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    folder: str = DEFAULT_FOLDER

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ImapConfig:
        env = os.environ if env is None else env
        missing = [name for name in ("CHEDDAR_IMAP_USER", "CHEDDAR_IMAP_PASSWORD")
                   if not env.get(name)]
        if missing:
            raise LoaderConfigError(
                "missing environment variable(s): " + ", ".join(missing))
        return cls(
            user=env["CHEDDAR_IMAP_USER"],
            password=env["CHEDDAR_IMAP_PASSWORD"],
            host=env.get("CHEDDAR_IMAP_HOST") or DEFAULT_HOST,
            folder=env.get("CHEDDAR_IMAP_FOLDER") or DEFAULT_FOLDER,
        )
