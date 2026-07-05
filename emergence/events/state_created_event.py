from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from emergence.core.event import Event, EventType


@dataclass(frozen=True, slots=True)
class StateCreatedEvent(Event):
    key: str = ""
    value: Any = None
    event_type: EventType = field(default=EventType.STATE_CREATED, init=False)