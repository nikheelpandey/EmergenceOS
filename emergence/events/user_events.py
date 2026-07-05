"""User interaction events for human-in-the-loop workflows."""

from __future__ import annotations

from dataclasses import dataclass, field

from emergence.core.event import Event, EventType
from emergence.core.ids import ProcessID


@dataclass(frozen=True, slots=True)
class UserMessageReceivedEvent(Event):
    message: str = ""
    event_type: EventType = field(
        default=EventType.USER_MESSAGE_RECEIVED,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class UserApprovalRequestedEvent(Event):
    request_id: str = ""
    message: str = ""
    event_type: EventType = field(
        default=EventType.USER_APPROVAL_REQUESTED,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class UserApprovalGrantedEvent(Event):
    request_id: str = ""
    event_type: EventType = field(
        default=EventType.USER_APPROVAL_GRANTED,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class EvaluationCompletedEvent(Event):
    score: int = 0
    approved: bool = False
    event_type: EventType = field(
        default=EventType.EVALUATION_COMPLETED,
        init=False,
    )
