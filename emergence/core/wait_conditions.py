from __future__ import annotations

from datetime import UTC, datetime

from emergence.core.wait_condition import WaitCondition
from emergence.kernel.mailbox_manager import MailboxManager
from emergence.kernel.state_store import StateStore


class MessageWaitCondition(WaitCondition):
    """
    Resume when the process mailbox has at least one message.
    """

    def __init__(
        self,
        pid: str,
        mailboxes: MailboxManager,
    ) -> None:
        self._pid = pid
        self._mailboxes = mailboxes

    def is_satisfied(self) -> bool:
        return self._mailboxes.pending(self._pid) > 0


class StateKeyWaitCondition(WaitCondition):
    """
    Resume when a state key exists in the StateStore.
    """

    def __init__(self, key: str, store: StateStore) -> None:
        self._key = key
        self._store = store

    def is_satisfied(self) -> bool:
        return self._store.exists(self._key)


class TimerWaitCondition(WaitCondition):
    """
    Resume after a wall-clock deadline has passed.
    """

    def __init__(self, wake_at: datetime) -> None:
        self._wake_at = wake_at

    def is_satisfied(self) -> bool:
        return datetime.now(UTC) >= self._wake_at
