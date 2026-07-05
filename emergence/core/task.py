from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from emergence.core.ids import PlanID, ProcessID, TaskID
from emergence.core.state import TASK_STATE_TRANSITIONS, TaskState


@dataclass(slots=True)
class Task:
    """
    Smallest schedulable unit of work within a plan.

    Tasks map to process instances via the scheduler.
    """

    plan_id: PlanID
    name: str
    process_definition_name: str
    task_id: TaskID = field(default_factory=TaskID.new)
    state: TaskState = TaskState.PENDING
    dependencies: tuple[TaskID, ...] = ()
    assigned_process_id: ProcessID | None = None
    expected_output: str = ""
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def transition_to(self, new_state: TaskState) -> None:
        if new_state == self.state:
            return
        allowed = TASK_STATE_TRANSITIONS[self.state]
        if new_state not in allowed:
            raise ValueError(
                f"Invalid task transition "
                f"{self.state.value} -> {new_state.value}"
            )
        self.state = new_state

    @property
    def is_finished(self) -> bool:
        return self.state in {
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        }

    @property
    def is_ready(self) -> bool:
        return self.state == TaskState.READY
