import imaplib
from email.message import EmailMessage
from typing import ClassVar


def build(sender="Bank <bank@example.com>", subject="Hi", date="Thu, 29 Oct 2026 18:01:51 -0400",
          message_id="<m1@x>", plain="plain body", html="<p>html body</p>"):
    msg = EmailMessage()
    msg["From"], msg["Subject"], msg["Date"] = sender, subject, date
    if message_id:
        msg["Message-ID"] = message_id
    msg.set_content(plain)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


class FakeIMAP:
    """Stands in for imaplib.IMAP4_SSL; records calls."""
    instances: ClassVar[list] = []
    messages: ClassVar[dict] = {}  # pending folder: uid -> bytes
    folders: ClassVar[dict] = {}  # destination folder name -> {uid: bytes}
    login_error = False
    select_status = "OK"
    store_status = "OK"
    copy_error = False
    errors: ClassVar[dict] = {}  # (command, uid or None) -> exception raised once
    drops: ClassVar[set] = set()  # (command, uid or None) at which a connection drops once
    reconnect_failure = None  # "connect", "login" or "select": fails after the first connection
    uidvalidity: ClassVar[list] = []  # one value per connection; the last one repeats

    def __init__(self, host, port, timeout=None):
        self._fail_reconnect("connect", bool(FakeIMAP.instances))
        self.timeout = timeout
        self.calls = []
        self._deleted = set()
        self._dropped = False
        FakeIMAP.instances.append(self)

    def _fail_reconnect(self, stage, is_reconnect):
        if is_reconnect and FakeIMAP.reconnect_failure == stage:
            raise OSError(f"{stage} timed out")

    def shutdown(self):
        self.calls.append(("shutdown",))

    def response(self, code):
        values = FakeIMAP.uidvalidity
        if not values:
            return code, [None]
        return code, [values[min(FakeIMAP.instances.index(self), len(values) - 1)]]

    def _check(self, command, uid=None):
        """Raise for an injected error, and on every call after a dropped connection."""
        if (command, uid) in FakeIMAP.drops:
            FakeIMAP.drops.remove((command, uid))
            self._dropped = True
        if self._dropped:
            raise imaplib.IMAP4.abort("connection dropped")
        if (command, uid) in FakeIMAP.errors:
            raise FakeIMAP.errors.pop((command, uid))

    def login(self, user, password):
        self._fail_reconnect("login", self is not FakeIMAP.instances[0])
        if FakeIMAP.login_error:
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")
        self.calls.append(("login", user))

    def logout(self):
        self._check("logout")
        self.calls.append(("logout",))

    def select(self, folder, readonly=False):
        self.calls.append(("select", folder, readonly))
        self._check("select")
        self._fail_reconnect("select", self is not FakeIMAP.instances[0])
        return FakeIMAP.select_status, [b""]

    def uid(self, command, *args):
        self.calls.append(("uid", command, *args))
        self._check(command, args[0] if command == "FETCH" else None)
        if command == "SEARCH":
            return "OK", [" ".join(FakeIMAP.messages).encode()]
        if command == "COPY":
            if FakeIMAP.copy_error:
                raise imaplib.IMAP4.error("COPY failed")
            uids, destination = args[0].split(","), args[1].strip('"')
            if destination not in FakeIMAP.folders:
                return "NO", [b"[TRYCREATE] no such folder"]
            for uid in uids:
                FakeIMAP.folders[destination][uid] = FakeIMAP.messages[uid]
            return "OK", [b"done"]
        if command == "STORE":
            if FakeIMAP.store_status == "OK":
                self._deleted.update(args[0].split(","))
            return FakeIMAP.store_status, [b"done"]
        uid = args[0]
        return "OK", [(b"1 (BODY[] {1}", FakeIMAP.messages[uid]), b")"]

    def expunge(self):
        self.calls.append(("expunge",))
        self._check("expunge")
        for uid in self._deleted:
            FakeIMAP.messages.pop(uid, None)
        self._deleted.clear()
        return "OK", [b"done"]
