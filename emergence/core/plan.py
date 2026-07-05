from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from emergence.core.ids import GoalID, PlanID
from emergence.core.state import PLAN_STATE_TRANSITIONS, PlanState


@dataclass(slots=True)
class Plan:
    """
    A decomposition of a goal into schedulable tasks.

    Plans evolve; goals do not.
    """

    goal_id: GoalID
    plan_id: PlanID = field(default_factory=PlanID.new)
    state: PlanState = PlanState.CREATED
    constraints: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def transition_to(self, new_state: PlanState) -> None:
        if new_state == self.state:
            return
        allowed = PLAN_STATE_TRANSITIONS[self.state]
        if new_state not in allowed:
            raise ValueError(
                f"Invalid plan transition "
                f"{self.state.value} -> {new_state.value}"
            )
        self.state = new_state

    @property
    def is_finished(self) -> bool:
        return self.state in {
            PlanState.COMPLETED,
            PlanState.FAILED,
            PlanState.CANCELLED,
        }
