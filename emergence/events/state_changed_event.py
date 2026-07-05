from dataclasses import dataclass, field
from emergence.core.event import Event, EventType
from typing import Any

@dataclass(frozen=True, slots=True)
class StateChangedEvent(Event):
    key: str = ""
    old_value: Any = None
    new_value: Any = None
    event_type: EventType = field(default=EventType.STATE_CHANGED, init=False)