from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any


class Mailbox:
    """
    A thread-safe FIFO mailbox owned by a single process.

    Processes communicate by sending messages to each other's
    mailboxes instead of calling one another directly.

    The kernel is responsible for creating and managing mailboxes.
    """

    def __init__(self) -> None:
        self._queue: deque[Any] = deque()
        self._lock = Lock()

    def send(self, message: Any) -> None:
        """
        Deliver a message to this mailbox.
        """
        with self._lock:
            self._queue.append(message)

    def receive(self) -> Any | None:
        """
        Retrieve the oldest pending message.

        Returns None if the mailbox is empty.
        """
        with self._lock:
            if not self._queue:
                return None

            return self._queue.popleft()

    def peek(self) -> Any | None:
        """
        Peek at the next message without removing it.
        """
        with self._lock:
            if not self._queue:
                return None

            return self._queue[0]

    def empty(self) -> bool:
        """
        Returns True if there are no pending messages.
        """
        with self._lock:
            return len(self._queue) == 0

    def size(self) -> int:
        """
        Return the number of pending messages.
        """
        with self._lock:
            return len(self._queue)

    def clear(self) -> None:
        """
        Remove all pending messages.
        """
        with self._lock:
            self._queue.clear()

    def __len__(self) -> int:
        return self.size()