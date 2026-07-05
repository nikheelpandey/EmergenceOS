from __future__ import annotations

from emergence.core.event import Event
from emergence.events.event_bus import EventBus
from emergence.events.event_store import EventStore


class PersistingEventBus(EventBus):
    """
    EventBus that appends every published event to an EventStore.
    """

    def __init__(self, event_store: EventStore) -> None:
        super().__init__()
        self._event_store = event_store

    @property
    def event_store(self) -> EventStore:
        return self._event_store

    def publish(self, event: Event) -> None:
        self._event_store.append(event)
        super().publish(event)
