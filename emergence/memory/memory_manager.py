from __future__ import annotations

from typing import Any

from emergence.core.ids import ProcessID
from emergence.events.event_bus import EventBus
from emergence.events.memory_events import (
    MemoryDeletedEvent,
    MemoryRetrievedEvent,
    MemoryStoredEvent,
)
from emergence.memory.memory_category import MemoryCategory
from emergence.memory.memory_store import MemoryStore


def _scoped_key(
    process_id: ProcessID,
    category: MemoryCategory,
    key: str,
) -> str:
    return f"{category.value}:{process_id}:{key}"


class MemoryManager:
    """
    Central owner of long-term memory.

    Processes never access MemoryStore directly — all operations
    flow through this manager and produce observable events.
    """

    def __init__(
        self,
        store: MemoryStore,
        event_bus: EventBus,
    ) -> None:
        self._store = store
        self._event_bus = event_bus

    def store(
        self,
        process_id: ProcessID,
        key: str,
        value: Any,
        *,
        category: MemoryCategory = MemoryCategory.WORKING,
    ) -> None:
        scoped = _scoped_key(process_id, category, key)
        self._store.set(scoped, value)
        self._event_bus.publish(
            MemoryStoredEvent(
                process_id=process_id,
                key=key,
                category=category,
                source_process=process_id,
                payload={"value": value},
            )
        )

    def retrieve(
        self,
        process_id: ProcessID,
        key: str,
        *,
        category: MemoryCategory = MemoryCategory.WORKING,
        default: Any = None,
    ) -> Any:
        scoped = _scoped_key(process_id, category, key)
        value = self._store.get(scoped, default)
        self._event_bus.publish(
            MemoryRetrievedEvent(
                process_id=process_id,
                key=key,
                category=category,
                source_process=process_id,
            )
        )
        return value

    def delete(
        self,
        process_id: ProcessID,
        key: str,
        *,
        category: MemoryCategory = MemoryCategory.WORKING,
    ) -> None:
        scoped = _scoped_key(process_id, category, key)
        if not self._store.exists(scoped):
            return
        self._store.delete(scoped)
        self._event_bus.publish(
            MemoryDeletedEvent(
                process_id=process_id,
                key=key,
                category=category,
                source_process=process_id,
            )
        )

    def exists(
        self,
        process_id: ProcessID,
        key: str,
        *,
        category: MemoryCategory = MemoryCategory.WORKING,
    ) -> bool:
        scoped = _scoped_key(process_id, category, key)
        return self._store.exists(scoped)

    def working_snapshot(self, process_id: ProcessID) -> dict[str, Any]:
        """Return all working-memory entries for a process."""
        prefix = f"{MemoryCategory.WORKING.value}:{process_id}:"
        result: dict[str, Any] = {}
        for scoped_key in self._store.keys():
            if scoped_key.startswith(prefix):
                short_key = scoped_key[len(prefix):]
                result[short_key] = self._store.get(scoped_key)
        return result
