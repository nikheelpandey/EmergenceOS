from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from emergence.core.event import Event, EventType
from emergence.core.ids import ArtifactID, GoalID, ProcessID


@dataclass(frozen=True, slots=True)
class ArtifactCreatedEvent(Event):
    artifact_id: ArtifactID | None = None
    artifact_type: str = ""
    name: str = ""
    version: int = 1
    goal_id: GoalID | None = None
    space_id: str = ""
    event_type: EventType = field(
        default=EventType.ARTIFACT_CREATED,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class ArtifactUpdatedEvent(Event):
    artifact_id: ArtifactID | None = None
    artifact_type: str = ""
    name: str = ""
    version: int = 1
    previous_version: int = 0
    goal_id: GoalID | None = None
    space_id: str = ""
    event_type: EventType = field(
        default=EventType.ARTIFACT_UPDATED,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class ArtifactDeletedEvent(Event):
    artifact_id: ArtifactID | None = None
    artifact_type: str = ""
    name: str = ""
    goal_id: GoalID | None = None
    space_id: str = ""
    event_type: EventType = field(
        default=EventType.ARTIFACT_DELETED,
        init=False,
    )


def artifact_event_payload(record: Any, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a standard artifact event payload from a record."""
    payload = {
        "artifact_id": str(record.artifact_id),
        "name": record.name,
        "artifact_type": record.artifact_type,
        "version": record.version,
        "goal_id": (
            str(record.owner_goal_id)
            if record.owner_goal_id is not None
            else None
        ),
        "space_id": record.space_id,
        "tags": list(record.tags),
        "status": record.status.value,
    }
    if extra:
        payload.update(extra)
    return payload
