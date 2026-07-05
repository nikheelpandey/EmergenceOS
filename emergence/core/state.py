"""
core/state.py

Defines lifecycle states for the core entities of EmergenceOS.

These enums describe the valid states that entities may occupy.
State transitions are validated using the transition maps defined
at the bottom of this file.

The Kernel is the only component permitted to change process state.
"""

from __future__ import annotations

from enum import Enum
from typing import Final


class ProcessState(str, Enum):
    """
    Lifecycle states for a Process.

    State transitions are managed exclusively by the Kernel.
    """

    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskState(str, Enum):
    """
    Lifecycle states for a Task.
    """

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GoalState(str, Enum):
    """
    Lifecycle states for a Goal.
    """

    CREATED = "created"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlanState(str, Enum):
    """
    Lifecycle states for a Plan.
    """

    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CheckpointState(str, Enum):
    """
    Lifecycle states for a Checkpoint.
    """

    CREATED = "created"
    STORED = "stored"
    RESTORED = "restored"




PROCESS_STATE_TRANSITIONS: Final[dict[ProcessState, set[ProcessState]]] = {
    ProcessState.CREATED: {
        ProcessState.READY,
        ProcessState.CANCELLED,
    },
    ProcessState.READY: {
        ProcessState.RUNNING,
        ProcessState.CANCELLED,
    },
    ProcessState.RUNNING: {
        ProcessState.WAITING,
        ProcessState.BLOCKED,
        ProcessState.COMPLETED,
        ProcessState.FAILED,
        ProcessState.CANCELLED,   # ADD THIS

    },
    ProcessState.WAITING: {
        ProcessState.READY,
        ProcessState.CANCELLED,
        ProcessState.FAILED,
    },
    ProcessState.BLOCKED: {
        ProcessState.READY,
        ProcessState.FAILED,
        ProcessState.CANCELLED,
    },
    ProcessState.COMPLETED: set(),
    ProcessState.FAILED: set(),
    ProcessState.CANCELLED: set(),
}


TASK_STATE_TRANSITIONS: Final[dict[TaskState, set[TaskState]]] = {
    TaskState.PENDING: {
        TaskState.READY,
        TaskState.CANCELLED,
    },
    TaskState.READY: {
        TaskState.RUNNING,
        TaskState.CANCELLED,
    },
    TaskState.RUNNING: {
        TaskState.COMPLETED,
        TaskState.FAILED,
    },
    TaskState.COMPLETED: set(),
    TaskState.FAILED: set(),
    TaskState.CANCELLED: set(),
}


GOAL_STATE_TRANSITIONS: Final[dict[GoalState, set[GoalState]]] = {
    GoalState.CREATED: {
        GoalState.PLANNING,
        GoalState.CANCELLED,
    },
    GoalState.PLANNING: {
        GoalState.IN_PROGRESS,
        GoalState.FAILED,
        GoalState.CANCELLED,
    },
    GoalState.IN_PROGRESS: {
        GoalState.COMPLETED,
        GoalState.FAILED,
        GoalState.CANCELLED,
    },
    GoalState.COMPLETED: set(),
    GoalState.FAILED: set(),
    GoalState.CANCELLED: set(),
}


PLAN_STATE_TRANSITIONS: Final[dict[PlanState, set[PlanState]]] = {
    PlanState.CREATED: {
        PlanState.ACTIVE,
        PlanState.CANCELLED,
    },
    PlanState.ACTIVE: {
        PlanState.COMPLETED,
        PlanState.FAILED,
        PlanState.CANCELLED,
    },
    PlanState.COMPLETED: set(),
    PlanState.FAILED: set(),
    PlanState.CANCELLED: set(),
}


CHECKPOINT_STATE_TRANSITIONS: Final[
    dict[CheckpointState, set[CheckpointState]]
] = {
    CheckpointState.CREATED: {
        CheckpointState.STORED,
    },
    CheckpointState.STORED: {
        CheckpointState.RESTORED,
    },
    CheckpointState.RESTORED: set(),
}


def is_valid_transition(current: Enum, new: Enum) -> bool:
    """
    Returns True if a state transition is allowed.

    Raises:
        TypeError:
            If the states belong to different enum types.
    """
    if type(current) is not type(new):
        raise TypeError(
            f"Cannot compare {type(current).__name__} "
            f"with {type(new).__name__}."
        )

    transition_maps = {
        ProcessState: PROCESS_STATE_TRANSITIONS,
        TaskState: TASK_STATE_TRANSITIONS,
        GoalState: GOAL_STATE_TRANSITIONS,
        PlanState: PLAN_STATE_TRANSITIONS,
        CheckpointState: CHECKPOINT_STATE_TRANSITIONS,
    }

    transitions = transition_maps[type(current)]
    return new in transitions[current]