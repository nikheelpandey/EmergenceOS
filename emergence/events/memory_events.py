from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from emergence.core.event import Event, EventType
from emergence.core.ids import ProcessID
from emergence.memory.memory_category import MemoryCategory


@dataclass(frozen=True, slots=True)
class MemoryStoredEvent(Event):
    process_id: ProcessID | None = None
    key: str = ""
    category: MemoryCategory = MemoryCategory.WORKING
    event_type: EventType = field(
        default=EventType.MEMORY_STORED,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class MemoryRetrievedEvent(Event):
    process_id: ProcessID | None = None
    key: str = ""
    category: MemoryCategory = MemoryCategory.WORKING
    event_type: EventType = field(
        default=EventType.MEMORY_RETRIEVED,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class MemoryDeletedEvent(Event):
    process_id: ProcessID | None = None
    key: str = ""
    category: MemoryCategory = MemoryCategory.WORKING
    event_type: EventType = field(
        default=EventType.MEMORY_DELETED,
        init=False,
    )
