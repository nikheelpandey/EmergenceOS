from __future__ import annotations

from emergence.common.message import Message
from emergence.kernel.mailbox_manager import MailboxManager
from emergence.security.capabilities import MESSAGE_SEND
from emergence.security.security_manager import SecurityManager


class GatedMailboxManager:
    """
    Capability-gated facade over MailboxManager.

    Sending messages requires MESSAGE_SEND. Receiving is always
    permitted for the owning process.
    """

    def __init__(
        self,
        mailboxes: MailboxManager,
        security: SecurityManager,
        pid: str,
    ) -> None:
        self._mailboxes = mailboxes
        self._security = security
        self._pid = pid

    def send(self, message: Message) -> None:
        self._security.require(
            self._pid,
            MESSAGE_SEND,
            operation=f"mailboxes.send(to={message.recipient_pid})",
        )
        self._mailboxes.send(message)

    def receive(self) -> Message | None:
        return self._mailboxes.receive(self._pid)

    def pending(self) -> int:
        return self._mailboxes.pending(self._pid)
