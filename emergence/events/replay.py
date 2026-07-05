from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from emergence.core.event import Event
from emergence.core.state import ProcessState
from emergence.events.event_store import EventStore


@dataclass
class ReplaySnapshot:
    """
    Kernel state reconstructed from an event log.
    """

    state: dict[str, Any] = field(default_factory=dict)
    process_states: dict[str, ProcessState] = field(default_factory=dict)
    event_count: int = 0


class ReplayEngine:
    """
    Reconstructs kernel state deterministically from the event log.
    """

    def __init__(self, event_store: EventStore) -> None:
        self._store = event_store

    def replay(self, since: datetime | None = None) -> ReplaySnapshot:
        snapshot = ReplaySnapshot()

        for event in self._store.replay(since=since):
            snapshot.event_count += 1
            self._apply(event, snapshot)

        return snapshot

    def _apply(self, event: Event, snapshot: ReplaySnapshot) -> None:
        from emergence.core.event import EventType

        if event.source_process is not None:
            pid = str(event.source_process)
            if event.event_type == EventType.PROCESS_CREATED:
                snapshot.process_states[pid] = ProcessState.CREATED
            elif event.event_type == EventType.PROCESS_READY:
                snapshot.process_states[pid] = ProcessState.READY
            elif event.event_type == EventType.PROCESS_STARTED:
                snapshot.process_states[pid] = ProcessState.RUNNING
            elif event.event_type == EventType.PROCESS_WAITING:
                snapshot.process_states[pid] = ProcessState.WAITING
            elif event.event_type == EventType.PROCESS_COMPLETED:
                snapshot.process_states[pid] = ProcessState.COMPLETED
            elif event.event_type == EventType.PROCESS_FAILED:
                snapshot.process_states[pid] = ProcessState.FAILED
            elif event.event_type == EventType.PROCESS_CANCELLED:
                snapshot.process_states[pid] = ProcessState.CANCELLED

        if event.event_type == EventType.STATE_CREATED:
            key = getattr(event, "key", None) or event.payload.get(
                "key"
            )
            value = getattr(event, "value", None) or event.payload.get(
                "value"
            )
            if key is not None:
                snapshot.state[key] = value
        elif event.event_type == EventType.STATE_CHANGED:
            key = getattr(event, "key", None) or event.payload.get(
                "key"
            )
            new_value = getattr(
                event, "new_value", None
            ) or event.payload.get("new_value")
            if key is not None:
                snapshot.state[key] = new_value
        elif event.event_type == EventType.STATE_DELETED:
            key = getattr(event, "key", None) or event.payload.get(
                "key"
            )
            snapshot.state.pop(key, None)
