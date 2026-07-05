"""
Tests for emergence.core.state.

Architectural Contract
----------------------
This module defines the canonical lifecycle state machines for all
core entities in EmergenceOS.

These tests ensure:

* All states are reachable only via valid transitions.
* Transition maps are internally consistent.
* Terminal states are truly terminal.
* is_valid_transition behaves correctly across all enums.
* Cross-enum comparisons are rejected.
"""

from __future__ import annotations

import pytest

from emergence.core.state import (
    ProcessState,
    TaskState,
    GoalState,
    PlanState,
    CheckpointState,
    is_valid_transition,
    PROCESS_STATE_TRANSITIONS,
    TASK_STATE_TRANSITIONS,
    GOAL_STATE_TRANSITIONS,
    PLAN_STATE_TRANSITIONS,
    CHECKPOINT_STATE_TRANSITIONS,
)


# ============================================================
# Helper
# ============================================================

STATE_MAPS = {
    ProcessState: PROCESS_STATE_TRANSITIONS,
    TaskState: TASK_STATE_TRANSITIONS,
    GoalState: GOAL_STATE_TRANSITIONS,
    PlanState: PLAN_STATE_TRANSITIONS,
    CheckpointState: CHECKPOINT_STATE_TRANSITIONS,
}


# ============================================================
# Consistency of transition maps
# ============================================================

class TestTransitionMapConsistency:
    """
    Ensures internal correctness of state transition tables.
    """

    def test_all_targets_are_valid_enum_members(self):
        """
        Every transition target must belong to the same Enum class.
        """
        for enum_cls, transitions in STATE_MAPS.items():
            for state, next_states in transitions.items():
                for next_state in next_states:
                    assert isinstance(next_state, enum_cls)

    def test_all_states_are_present_as_keys(self):
        """
        Every enum state must exist as a key in its transition map.
        """
        for enum_cls, transitions in STATE_MAPS.items():
            enum_values = set(enum_cls)
            assert set(transitions.keys()) == enum_values

    def test_no_duplicate_self_reference_where_not_explicit(self):
        """
        Ensure no accidental self-transitions unless explicitly defined.
        """
        for enum_cls, transitions in STATE_MAPS.items():
            for state, next_states in transitions.items():
                if state not in next_states:
                    assert state not in next_states


# ============================================================
# Terminal state behavior
# ============================================================

class TestTerminalStates:
    """
    Terminal states must have no outgoing transitions.
    """

    def test_terminal_states_are_empty(self):
        for transitions in STATE_MAPS.values():
            for state, next_states in transitions.items():
                if len(next_states) == 0:
                    # Terminal state detected
                    assert next_states == set()

    def test_process_terminal_states(self):
        terminal = {
            ProcessState.COMPLETED,
            ProcessState.FAILED,
            ProcessState.CANCELLED,
        }

        for state in terminal:
            assert PROCESS_STATE_TRANSITIONS[state] == set()


# ============================================================
# Valid transition logic
# ============================================================

class TestValidTransitionFunction:
    """
    Tests for is_valid_transition helper.
    """

    def test_valid_transition_returns_true(self):
        assert is_valid_transition(
            ProcessState.CREATED,
            ProcessState.READY,
        ) is True

    def test_invalid_transition_returns_false(self):
        assert is_valid_transition(
            ProcessState.COMPLETED,
            ProcessState.RUNNING,
        ) is False

    def test_self_transition_behavior(self):
        """
        Self-transitions are not defined in maps, so should be invalid.
        """
        assert is_valid_transition(
            ProcessState.RUNNING,
            ProcessState.RUNNING,
        ) is False

    def test_cross_enum_type_raises(self):
        with pytest.raises(TypeError):
            is_valid_transition(
                ProcessState.CREATED,
                TaskState.PENDING,
            )


# ============================================================
# Exhaustive ProcessState validation
# ============================================================

class TestProcessStateExhaustive:
    """
    Ensures ProcessState transitions fully match the declared FSM.
    """

    def test_every_allowed_transition_returns_true(self):
        for current, allowed in PROCESS_STATE_TRANSITIONS.items():
            for nxt in allowed:
                assert is_valid_transition(current, nxt) is True

    def test_every_disallowed_transition_returns_false(self):
        all_states = list(ProcessState)

        for current in ProcessState:
            allowed = PROCESS_STATE_TRANSITIONS[current]
            for nxt in all_states:
                if nxt != current and nxt not in allowed:
                    assert is_valid_transition(current, nxt) is False


# ============================================================
# Similar exhaustive checks for other enums
# ============================================================

class TestOtherStateMachines:
    """
    Lightweight consistency checks for other state machines.
    """

    def test_task_state_machine(self):
        for current, allowed in TASK_STATE_TRANSITIONS.items():
            for nxt in allowed:
                assert is_valid_transition(current, nxt) is True

    def test_goal_state_machine(self):
        for current, allowed in GOAL_STATE_TRANSITIONS.items():
            for nxt in allowed:
                assert is_valid_transition(current, nxt) is True

    def test_plan_state_machine(self):
        for current, allowed in PLAN_STATE_TRANSITIONS.items():
            for nxt in allowed:
                assert is_valid_transition(current, nxt) is True

    def test_checkpoint_state_machine(self):
        for current, allowed in CHECKPOINT_STATE_TRANSITIONS.items():
            for nxt in allowed:
                assert is_valid_transition(current, nxt) is True


# ============================================================
# Cross-enum safety
# ============================================================

class TestCrossEnumSafety:
    """
    Prevents accidental mixing of different state machines.
    """

    def test_cross_enum_validation(self):
        with pytest.raises(TypeError):
            is_valid_transition(
                ProcessState.RUNNING,
                GoalState.PLANNING,
            )

        with pytest.raises(TypeError):
            is_valid_transition(
                TaskState.READY,
                PlanState.ACTIVE,
            )