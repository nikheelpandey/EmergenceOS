"""
core/event.py

Defines the Event model and EventType enumeration.

Events are immutable records describing facts that have occurred within
EmergenceOS. They form the backbone of communication between processes
and provide the foundation for observability, replay, auditing, and
event sourcing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from emergence.core.ids import EventID, ProcessID


class EventType(str, Enum):
    """
    Canonical event types understood by the kernel.
    """

    # ------------------------------------------------------------------
    # Process Events
    # ------------------------------------------------------------------

    PROCESS_CREATED = "process.created"
    PROCESS_READY = "process.ready"
    PROCESS_STARTED = "process.started"
    PROCESS_WAITING = "process.waiting"
    PROCESS_BLOCKED = "process.blocked"
    PROCESS_COMPLETED = "process.completed"
    PROCESS_FAILED = "process.failed"
    PROCESS_CANCELLED = "process.cancelled"

    # ------------------------------------------------------------------
    # Task Events
    # ------------------------------------------------------------------

    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"

    # ------------------------------------------------------------------
    # Goal Events
    # ------------------------------------------------------------------

    GOAL_CREATED = "goal.created"
    GOAL_COMPLETED = "goal.completed"
    GOAL_FAILED = "goal.failed"

    # ------------------------------------------------------------------
    # Plan Events
    # ------------------------------------------------------------------

    PLAN_CREATED = "plan.created"
    PLAN_UPDATED = "plan.updated"
    PLAN_COMPLETED = "plan.completed"

    # ------------------------------------------------------------------
    # Memory Events
    # ------------------------------------------------------------------

    MEMORY_STORED = "memory.stored"
    MEMORY_RETRIEVED = "memory.retrieved"
    MEMORY_DELETED = "memory.deleted"

    # ------------------------------------------------------------------
    # Executor Events
    # ------------------------------------------------------------------

    TOOL_REQUESTED = "tool.requested"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"

    # ------------------------------------------------------------------
    # Checkpoint Events
    # ------------------------------------------------------------------

    CHECKPOINT_CREATED = "checkpoint.created"
    CHECKPOINT_RESTORED = "checkpoint.restored"

    # ------------------------------------------------------------------
    # Scheduler Events
    # ------------------------------------------------------------------

    PROCESS_SCHEDULED = "process.scheduled"
    PROCESS_DISPATCHED = "process.dispatched"

    # ------------------------------------------------------------------
    # Kernel Events
    # ------------------------------------------------------------------

    KERNEL_STARTED = "kernel.started"
    KERNEL_STOPPED = "kernel.stopped"

    # ------------------------------------------------------------------
    # User Events
    # ------------------------------------------------------------------

    USER_INPUT = "user.input"
    USER_APPROVED = "user.approved"
    USER_CANCELLED = "user.cancelled"


@dataclass(frozen=True, slots=True)
class Event:
    """
    Immutable representation of something that has occurred.

    Events are historical facts.
    """

    # ------------------------------------------------------------------
    # Required fields
    # ------------------------------------------------------------------

    event_type: EventType

    # ------------------------------------------------------------------
    # Optional metadata
    # ------------------------------------------------------------------

    source_process: ProcessID | None = None
    correlation_id: UUID | None = None
    causation_id: EventID | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Automatically generated fields
    # ------------------------------------------------------------------

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_id: EventID = field(default_factory=EventID.new)

    @property
    def is_root(self) -> bool:
        """Return True if this event has no causation."""
        return self.causation_id is None

    def to_dict(self) -> dict[str, Any]:
        """Convert the event to a JSON-serializable dictionary."""

        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "source_process": (
                str(self.source_process)
                if self.source_process is not None
                else None
            ),
            "correlation_id": (
                str(self.correlation_id)
                if self.correlation_id is not None
                else None
            ),
            "causation_id": (
                str(self.causation_id)
                if self.causation_id is not None
                else None
            ),
            "payload": self.payload,
        }

    def __repr__(self) -> str:
        return (
            f"Event("
            f"id={self.event_id}, "
            f"type={self.event_type.value}, "
            f"source={self.source_process})"
        )