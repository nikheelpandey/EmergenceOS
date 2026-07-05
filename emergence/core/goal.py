from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from emergence.core.ids import GoalID
from emergence.core.state import GOAL_STATE_TRANSITIONS, GoalState


@dataclass(slots=True)
class Goal:
    """
    Represents an intended outcome.

    Goals are immutable in description but their lifecycle state
    evolves through kernel-managed transitions.
    """

    description: str
    goal_id: GoalID = field(default_factory=GoalID.new)
    state: GoalState = GoalState.CREATED
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def transition_to(self, new_state: GoalState) -> None:
        if new_state == self.state:
            return
        allowed = GOAL_STATE_TRANSITIONS[self.state]
        if new_state not in allowed:
            raise ValueError(
                f"Invalid goal transition "
                f"{self.state.value} -> {new_state.value}"
            )
        self.state = new_state

    @property
    def is_finished(self) -> bool:
        return self.state in {
            GoalState.COMPLETED,
            GoalState.FAILED,
            GoalState.CANCELLED,
        }
