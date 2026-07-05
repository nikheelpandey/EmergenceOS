"""
core/process.py

Defines the Process model.

A Process represents a running instance of a ProcessDefinition.

Unlike a ProcessDefinition, which is immutable and describes *what* a
process is, a Process represents the runtime state managed by the Kernel.

The Process intentionally owns only its identity and lifecycle.
Subsystem-specific runtime state (memory, checkpoints, metrics, scheduling,
etc.) is owned by their respective managers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from emergence.core.budget import ResourceBudget
from emergence.core.ids import (
    GoalID,
    ProcessDefinitionID,
    ProcessID,
)
from emergence.core.process_definition import ProcessDefinition
from emergence.core.state import (
    PROCESS_STATE_TRANSITIONS,
    ProcessState,
)


@dataclass(slots=True)
class Process:
    """
    Runtime instance of a ProcessDefinition.
    """

    # ------------------------------------------------------------------
    # Required fields
    # ------------------------------------------------------------------

    definition: ProcessDefinition

    # ------------------------------------------------------------------
    # Optional constructor arguments
    # ------------------------------------------------------------------

    goal_id: GoalID | None = None

    budget: ResourceBudget = field(default_factory=ResourceBudget)

    parent_process_id: ProcessID | None = None

    # ------------------------------------------------------------------
    # Runtime state
    # ------------------------------------------------------------------

    state: ProcessState = ProcessState.CREATED

    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    started_at: datetime | None = None

    completed_at: datetime | None = None

    failure_reason: str | None = None

    # ------------------------------------------------------------------
    # Generated identity
    # ------------------------------------------------------------------

    process_id: ProcessID = field(default_factory=ProcessID.new)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def transition_to(self, new_state: ProcessState) -> None:
        if new_state == self.state:
            return  # idempotent no-op

        allowed = PROCESS_STATE_TRANSITIONS[self.state]

        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition {self.state.value} -> {new_state.value}"
            )

        self.state = new_state

        now = datetime.now(UTC)

        if (
            new_state == ProcessState.RUNNING
            and self.started_at is None
        ):
            self.started_at = now

        if new_state in (
            ProcessState.COMPLETED,
            ProcessState.FAILED,
            ProcessState.CANCELLED,
        ):
            self.completed_at = now

    def start(self) -> None:
        """Transition the process to RUNNING."""
        self.transition_to(ProcessState.RUNNING)

    def complete(self) -> None:
        """Transition the process to COMPLETED."""
        self.transition_to(ProcessState.COMPLETED)

    def fail(self, reason: str | None = None) -> None:
        """Transition the process to FAILED."""
        self.transition_to(ProcessState.FAILED)
        self.failure_reason = reason

    def cancel(self) -> None:
        """Transition the process to CANCELLED."""
        self.transition_to(ProcessState.CANCELLED)

    # ------------------------------------------------------------------
    # Convenience Properties
    # ------------------------------------------------------------------

    @property
    def process_definition_id(self) -> ProcessDefinitionID:
        """Return the ProcessDefinition identifier."""
        return self.definition.process_definition_id

    @property
    def is_finished(self) -> bool:
        """Return True if the process has reached a terminal state."""
        return self.state in {
            ProcessState.COMPLETED,
            ProcessState.FAILED,
            ProcessState.CANCELLED,
        }

    @property
    def is_running(self) -> bool:
        """Return True if the process is currently executing."""
        return self.state == ProcessState.RUNNING

    @property
    def is_ready(self) -> bool:
        """Return True if the process is ready for scheduling."""
        return self.state == ProcessState.READY

    @property
    def age_seconds(self) -> float:
        """Return the process age in seconds."""
        return (
            datetime.now(UTC) - self.created_at
        ).total_seconds()

    def __repr__(self) -> str:
        return (
            f"Process("
            f"id={self.process_id}, "
            f"name='{self.definition.name}', "
            f"state={self.state.value})"
        )