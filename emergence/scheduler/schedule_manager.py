from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from emergence.core.event import Event, EventType
from emergence.core.ids import GoalID, ProcessID
from emergence.events.event_bus import EventBus

if TYPE_CHECKING:
    from emergence.kernel.kernel import Kernel


@dataclass(slots=True)
class ScheduledEntry:
    schedule_id: str
    goal_id: GoalID
    process_definition_name: str
    fire_at: datetime
    description: str
    fired: bool = False


@dataclass
class ScheduleManager:
    """Registers future wakeups tied to goals."""

    event_bus: EventBus
    _entries: dict[str, ScheduledEntry] = field(default_factory=dict)

    def register(
        self,
        goal_id: GoalID,
        process_definition_name: str,
        fire_at: datetime,
        *,
        description: str = "",
    ) -> ScheduledEntry:
        schedule_id = str(uuid4())
        entry = ScheduledEntry(
            schedule_id=schedule_id,
            goal_id=goal_id,
            process_definition_name=process_definition_name,
            fire_at=fire_at,
            description=description or f"Scheduled {process_definition_name}",
        )
        self._entries[schedule_id] = entry
        self.event_bus.publish(
            Event(
                event_type=EventType.PROCESS_SCHEDULED,
                payload={
                    "schedule_id": schedule_id,
                    "goal_id": str(goal_id),
                    "process_definition_name": process_definition_name,
                    "fire_at": fire_at.isoformat(),
                    "description": entry.description,
                    "action": "registered",
                },
            )
        )
        return entry

    def pending_for_goal(self, goal_id: GoalID) -> list[ScheduledEntry]:
        return [
            entry
            for entry in self._entries.values()
            if entry.goal_id == goal_id and not entry.fired
        ]

    def pending_all(self) -> list[ScheduledEntry]:
        return [entry for entry in self._entries.values() if not entry.fired]

    def process_due(self, kernel: Kernel, *, now: datetime | None = None) -> list[str]:
        """Fire due schedules and return spawned process ids."""
        current = now or datetime.now(UTC)
        spawned: list[str] = []

        for entry in list(self.pending_all()):
            if entry.fire_at > current:
                continue
            process = self._fire_entry(kernel, entry)
            spawned.append(str(process.process_id))

        return spawned

    def _fire_entry(self, kernel: Kernel, entry: ScheduledEntry) -> Any:
        ctx = kernel.context
        definition = ctx.registry.get(entry.process_definition_name)
        process = kernel.spawn(
            definition,
            goal_id=entry.goal_id,
            priority=6,
        )
        entry.fired = True
        self.event_bus.publish(
            Event(
                event_type=EventType.PROCESS_SCHEDULED,
                source_process=process.process_id,
                payload={
                    "schedule_id": entry.schedule_id,
                    "goal_id": str(entry.goal_id),
                    "process_definition_name": entry.process_definition_name,
                    "fire_at": entry.fire_at.isoformat(),
                    "description": entry.description,
                    "action": "fired",
                    "process_id": str(process.process_id),
                },
            )
        )
        return process

    def snapshot(self) -> dict[str, Any]:
        return {
            "entries": [
                {
                    "schedule_id": entry.schedule_id,
                    "goal_id": str(entry.goal_id),
                    "process_definition_name": entry.process_definition_name,
                    "fire_at": entry.fire_at.isoformat(),
                    "description": entry.description,
                    "fired": entry.fired,
                }
                for entry in self._entries.values()
            ]
        }

    def restore(self, data: dict[str, Any]) -> None:
        self._entries.clear()
        for raw in data.get("entries", []):
            entry = ScheduledEntry(
                schedule_id=str(raw["schedule_id"]),
                goal_id=GoalID.from_string(str(raw["goal_id"])),
                process_definition_name=str(raw["process_definition_name"]),
                fire_at=datetime.fromisoformat(str(raw["fire_at"])),
                description=str(raw.get("description", "")),
                fired=bool(raw.get("fired", False)),
            )
            self._entries[entry.schedule_id] = entry
