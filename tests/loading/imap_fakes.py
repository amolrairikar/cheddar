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
    messages: ClassVar[dict] = {}  # uid -> bytes
    login_error = False
    select_status = "OK"

    def __init__(self, host, port):
        self.calls = []
        FakeIMAP.instances.append(self)

    def login(self, user, password):
        if FakeIMAP.login_error:
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")
        self.calls.append(("login", user))

    def logout(self):
        self.calls.append(("logout",))

    def select(self, folder, readonly=False):
        self.calls.append(("select", folder, readonly))
        return FakeIMAP.select_status, [b""]

    def uid(self, command, *args):
        self.calls.append(("uid", command, *args))
        if command == "SEARCH":
            return "OK", [" ".join(FakeIMAP.messages).encode()]
        uid = args[0]
        return "OK", [(b"1 (BODY[] {1}", FakeIMAP.messages[uid]), b")"]
