from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from emergence.core.event import Event, EventType
from emergence.core.ids import EventID, ProcessID


class EventStore:
    """
    Append-only event log for deterministic replay.

    Every event published through the kernel is persisted here.
    """

    def __init__(self) -> None:
        self._events: list[Event] = []

    def append(self, event: Event) -> None:
        """Append an immutable event to the log."""
        self._events.append(event)

    def query(
        self,
        *,
        event_type: EventType | None = None,
        source_process: ProcessID | None = None,
        correlation_id: UUID | None = None,
        since: datetime | None = None,
    ) -> list[Event]:
        """Query events with optional filters."""
        results = list(self._events)

        if event_type is not None:
            results = [
                e for e in results if e.event_type == event_type
            ]
        if source_process is not None:
            results = [
                e
                for e in results
                if e.source_process == source_process
            ]
        if correlation_id is not None:
            results = [
                e
                for e in results
                if e.correlation_id == correlation_id
            ]
        if since is not None:
            results = [e for e in results if e.timestamp >= since]

        return results

    def replay(self, since: datetime | None = None) -> list[Event]:
        """Return events in append order, optionally from a timestamp."""
        if since is None:
            return list(self._events)
        return [e for e in self._events if e.timestamp >= since]

    def count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        self._events.clear()

    def to_dicts(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self._events]


class JsonlEventStore(EventStore):
    """File-backed event store using JSON Lines format."""

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists():
            self._load()

    def append(self, event: Event) -> None:
        super().append(event)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_dict()) + "\n")

    def _load(self) -> None:
        with self._path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                self._events.append(_event_from_dict(data))


def _event_from_dict(data: dict[str, Any]) -> Event:
    return Event(
        event_type=EventType(data["event_type"]),
        source_process=(
            ProcessID(data["source_process"])
            if data.get("source_process")
            else None
        ),
        correlation_id=(
            UUID(data["correlation_id"])
            if data.get("correlation_id")
            else None
        ),
        causation_id=(
            EventID(data["causation_id"])
            if data.get("causation_id")
            else None
        ),
        payload=data.get("payload", {}),
        timestamp=datetime.fromisoformat(data["timestamp"]),
        event_id=EventID(data["event_id"]),
    )
