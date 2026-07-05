from __future__ import annotations

from dataclasses import dataclass, field

from emergence.common.message import Message
from emergence.core.event import Event, EventType


@dataclass(frozen=True, slots=True)
class MessageReceivedEvent(Event):
    """
    Published whenever a message is delivered to a process mailbox.

    The scheduler can subscribe to this event to wake processes
    waiting for incoming messages.
    """

    recipient_pid: str = ""
    message: Message | None = None
    event_type: EventType = field(
        default=EventType.MESSAGE_RECEIVED,
        init=False,
    )
