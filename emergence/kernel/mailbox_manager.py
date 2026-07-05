from __future__ import annotations

from emergence.common.message import Message
from emergence.events.event_bus import EventBus
from emergence.events.message_received_event import MessageReceivedEvent
from emergence.kernel.mailbox import Mailbox


class MailboxManager:
    """
    Owns and manages every mailbox in the system.

    Processes never communicate directly with one another.
    Instead, the kernel routes messages to the appropriate mailbox.
    """

    def __init__(self, event_bus: EventBus):
        self._mailboxes: dict[str, Mailbox] = {}
        self._event_bus = event_bus

    def create(self, pid: str) -> None:
        """
        Create a mailbox for a process.
        """
        if pid not in self._mailboxes:
            self._mailboxes[pid] = Mailbox()

    def delete(self, pid: str) -> None:
        """
        Remove a process mailbox.
        """
        self._mailboxes.pop(pid, None)

    def exists(self, pid: str) -> bool:
        """
        Return True if the process has a mailbox.
        """
        return pid in self._mailboxes

    def mailbox(self, pid: str) -> Mailbox:
        """
        Return the mailbox for a process.
        """
        return self._mailboxes[pid]

    def send(self, message: Message) -> None:
        """
        Deliver a message to a process.
        """

        mailbox = self._mailboxes.get(message.recipient_pid)

        if mailbox is None:
            raise KeyError(
                f"No mailbox exists for process '{message.recipient_pid}'."
            )

        mailbox.send(message)

        self._event_bus.publish(
            MessageReceivedEvent(
                recipient_pid=message.recipient_pid,
                message=message,
            )
        )

    def receive(self, pid: str) -> Message | None:
        """
        Receive the next pending message.
        """

        mailbox = self._mailboxes.get(pid)

        if mailbox is None:
            return None

        return mailbox.receive()

    def pending(self, pid: str) -> int:
        """
        Return the number of pending messages.
        """

        mailbox = self._mailboxes.get(pid)

        if mailbox is None:
            return 0

        return len(mailbox)

    def clear(self) -> None:
        """
        Remove every mailbox.
        """
        self._mailboxes.clear()