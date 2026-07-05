from __future__ import annotations

from dataclasses import dataclass, field

from emergence.checkpoint.checkpoint import Checkpoint
from emergence.core.event import Event, EventType
from emergence.core.ids import ProcessID


@dataclass(frozen=True, slots=True)
class CheckpointCreatedEvent(Event):
    checkpoint_id: str = ""
    process_id: ProcessID | None = None
    event_type: EventType = field(
        default=EventType.CHECKPOINT_CREATED,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class CheckpointRestoredEvent(Event):
    checkpoint_id: str = ""
    process_id: ProcessID | None = None
    event_type: EventType = field(
        default=EventType.CHECKPOINT_RESTORED,
        init=False,
    )
