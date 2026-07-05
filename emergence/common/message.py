from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(slots=True, kw_only=True)
class Message:
    """
    Base class for all inter-process communication (IPC).

    Messages are immutable pieces of information exchanged between
    processes through kernel-managed mailboxes.
    """

    sender_pid: str
    recipient_pid: str
    payload: object | None = None

    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
