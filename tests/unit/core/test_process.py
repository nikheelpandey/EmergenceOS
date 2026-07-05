"""
Tests for emergence.core.process.

Architectural Contract
----------------------
A Process represents the runtime instance of a ProcessDefinition.

Unlike ProcessDefinition, a Process owns mutable runtime state and is
responsible for enforcing lifecycle transitions defined by the kernel.

These tests protect the following invariants:

* Every Process has a unique identity.
* Every Process starts in a valid initial state.
* Runtime metadata is initialized correctly.
* Legal lifecycle transitions succeed.
* Lifecycle timestamps are recorded correctly.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from emergence.core.budget import ResourceBudget
from emergence.core.ids import GoalID, ProcessID
from emergence.core.process import Process
from emergence.core.process_definition import ProcessDefinition
from emergence.core.state import (
    PROCESS_STATE_TRANSITIONS,
    ProcessState,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def process_definition() -> ProcessDefinition:
    """
    Return a minimal valid ProcessDefinition.

    Individual tests should override values only when necessary.
    """
    return ProcessDefinition(
        name="Planner",
        implementation="planner.process",
    )


# ============================================================================
# Construction
# ============================================================================


class TestConstruction:
    """
    Verify Process construction.

    A newly created Process should always begin life in a valid runtime
    state before being scheduled by the kernel.
    """

    def test_minimal_process(self, process_definition):
        process = Process(definition=process_definition)

        assert process.definition is process_definition

        assert isinstance(process.process_id, ProcessID)

        assert process.goal_id is None
        assert process.parent_process_id is None

        assert isinstance(process.budget, ResourceBudget)

        assert process.state is ProcessState.CREATED

        assert process.started_at is None
        assert process.completed_at is None
        assert process.failure_reason is None

    def test_custom_constructor_arguments(self, process_definition):
        goal = GoalID.new()
        parent = ProcessID.new()

        budget = ResourceBudget(
            max_tokens=5000,
            max_memory_mb=1024,
        )

        process = Process(
            definition=process_definition,
            goal_id=goal,
            parent_process_id=parent,
            budget=budget,
        )

        assert process.goal_id == goal
        assert process.parent_process_id == parent
        assert process.budget == budget

    def test_created_timestamp_is_populated(self, process_definition):
        process = Process(definition=process_definition)

        assert isinstance(process.created_at, datetime)
        assert process.created_at.tzinfo == UTC

    def test_every_process_receives_unique_process_id(
        self,
        process_definition,
    ):
        process1 = Process(definition=process_definition)
        process2 = Process(definition=process_definition)

        assert process1.process_id != process2.process_id


# ============================================================================
# Initial State
# ============================================================================


class TestInitialState:
    """
    Every Process must begin in the CREATED state.

    No timestamps except created_at should be populated until lifecycle
    transitions occur.
    """

    def test_process_starts_created(self, process_definition):
        process = Process(definition=process_definition)

        assert process.state is ProcessState.CREATED

    def test_process_is_not_running(self, process_definition):
        process = Process(definition=process_definition)

        assert not process.is_running

    def test_process_is_not_ready(self, process_definition):
        process = Process(definition=process_definition)

        assert not process.is_ready

    def test_process_is_not_finished(self, process_definition):
        process = Process(definition=process_definition)

        assert not process.is_finished


# ============================================================================
# Legal Lifecycle Transitions
# ============================================================================


class TestLifecycleTransitions:
    """
    Verify that every legal lifecycle transition succeeds.

    Rather than testing kernel behavior, these tests verify the Process
    correctly updates its own runtime state.
    """

    @pytest.mark.parametrize(
        ("current_state", "next_state"),
        [
            (current, target)
            for current, allowed in PROCESS_STATE_TRANSITIONS.items()
            for target in allowed
        ],
    )
    def test_every_legal_transition_succeeds(
        self,
        process_definition,
        current_state,
        next_state,
    ):
        process = Process(definition=process_definition)

        process.state = current_state

        process.transition_to(next_state)

        assert process.state is next_state

    def test_running_transition_sets_started_timestamp(
        self,
        process_definition,
    ):
        process = Process(definition=process_definition)

        process.state = ProcessState.READY

        process.start()

        assert process.state is ProcessState.RUNNING
        assert process.started_at is not None

    @pytest.mark.parametrize(
        "terminal_state",
        [
            ProcessState.COMPLETED,
            ProcessState.FAILED,
            ProcessState.CANCELLED,
        ],
    )
    def test_terminal_transition_sets_completed_timestamp(
        self,
        process_definition,
        terminal_state,
    ):
        process = Process(definition=process_definition)

        #
        # Move through a legal path.
        #
        process.state = ProcessState.RUNNING

        process.transition_to(terminal_state)

        assert process.completed_at is not None
        assert process.state is terminal_state


    def test_idempotent_transition_is_noop(
        self,
        process_definition,
    ):
        process = Process(definition=process_definition)

        process.state = ProcessState.RUNNING

        process.transition_to(ProcessState.RUNNING)

        assert process.state is ProcessState.RUNNING


# ============================================================================
# Illegal Lifecycle Transitions
# ============================================================================


class TestIllegalLifecycleTransitions:
    """
    Verify that illegal lifecycle transitions are rejected.

    Rather than hard-coding invalid transitions, these tests derive them from
    the kernel's transition table. If the lifecycle evolves, these tests
    automatically evolve with it.
    """

    @pytest.mark.parametrize(
        ("current_state", "next_state"),
        [
            (current, candidate)
            for current in ProcessState
            for candidate in ProcessState
            if candidate not in PROCESS_STATE_TRANSITIONS[current]
            and candidate != current
        ],
    )
    def test_illegal_transition_raises(
        self,
        process_definition,
        current_state,
        next_state,
    ):
        process = Process(definition=process_definition)

        process.state = current_state

        with pytest.raises(
            ValueError,
            match=f"Invalid transition {current_state.value} -> {next_state.value}",
        ):
            process.transition_to(next_state)


# ============================================================================
# Convenience Methods
# ============================================================================


class TestConvenienceMethods:
    """
    Convenience methods are thin wrappers around transition_to().

    These tests ensure they move the Process into the expected lifecycle
    state and update timestamps where appropriate.
    """

    def test_start_transitions_to_running(self, process_definition):
        process = Process(definition=process_definition)

        process.state = ProcessState.READY

        process.start()

        assert process.state is ProcessState.RUNNING
        assert process.started_at is not None

    def test_complete_transitions_to_completed(self, process_definition):
        process = Process(definition=process_definition)

        process.state = ProcessState.RUNNING

        process.complete()

        assert process.state is ProcessState.COMPLETED
        assert process.completed_at is not None

    def test_fail_transitions_to_failed(self, process_definition):
        process = Process(definition=process_definition)

        process.state = ProcessState.RUNNING

        process.fail("boom")

        assert process.state is ProcessState.FAILED
        assert process.failure_reason == "boom"
        assert process.completed_at is not None

    def test_fail_without_reason(self, process_definition):
        process = Process(definition=process_definition)

        process.state = ProcessState.RUNNING

        process.fail()

        assert process.state is ProcessState.FAILED
        assert process.failure_reason is None

    def test_cancel_transitions_to_cancelled(self, process_definition):
        process = Process(definition=process_definition)

        process.state = ProcessState.RUNNING

        process.cancel()

        assert process.state is ProcessState.CANCELLED
        assert process.completed_at is not None


# ============================================================================
# Timestamp Behaviour
# ============================================================================


class TestTimestampBehaviour:
    """
    Lifecycle timestamps should only be populated by the appropriate
    transitions.
    """

    def test_start_does_not_modify_completed_timestamp(
        self,
        process_definition,
    ):
        process = Process(definition=process_definition)

        process.state = ProcessState.READY

        process.start()

        assert process.completed_at is None

    def test_complete_preserves_started_timestamp(
        self,
        process_definition,
    ):
        process = Process(definition=process_definition)

        process.state = ProcessState.READY
        process.start()

        started_at = process.started_at

        process.complete()

        assert process.started_at == started_at

    def test_started_timestamp_only_set_once(
        self,
        process_definition,
    ):
        process = Process(definition=process_definition)

        process.state = ProcessState.READY
        process.start()

        first_started = process.started_at

        #
        # Simulate a repeated RUNNING transition.
        #
        process.transition_to(ProcessState.RUNNING)

        assert process.started_at == first_started


# ============================================================================
# Failure Handling
# ============================================================================


class TestFailureHandling:
    """
    Failure-specific behaviour.

    These tests verify that failure metadata is recorded consistently.
    """

    def test_failure_reason_defaults_to_none(self, process_definition):
        process = Process(definition=process_definition)

        assert process.failure_reason is None

    def test_failure_reason_is_recorded(self, process_definition):
        process = Process(definition=process_definition)

        process.state = ProcessState.RUNNING

        process.fail("LLM timeout")

        assert process.failure_reason == "LLM timeout"

    def test_failure_reason_can_be_empty_string(
        self,
        process_definition,
    ):
        process = Process(definition=process_definition)

        process.state = ProcessState.RUNNING

        process.fail("")

        assert process.failure_reason == ""


# ============================================================================
# Regression Tests
# ============================================================================


class TestRegression:
    """
    Regression tests protect against bugs that have previously been found.

    These tests should never be removed.
    """

    def test_failed_transition_does_not_mutate_failure_reason(
        self,
        process_definition,
    ):
        """
        If fail() raises because the transition is illegal, the Process
        should remain completely unchanged.
        """
        process = Process(definition=process_definition)

        process.state = ProcessState.COMPLETED

        with pytest.raises(ValueError):
            process.fail("boom")

        assert process.failure_reason is None

# ============================================================================
# Convenience Properties
# ============================================================================


class TestConvenienceProperties:
    """
    Convenience properties expose commonly queried runtime information.

    These tests protect the public API used by the scheduler, executor,
    kernel, and monitoring components.
    """

    def test_process_definition_id_returns_definition_identifier(
        self,
        process_definition,
    ):
        process = Process(definition=process_definition)

        assert (
            process.process_definition_id
            == process.definition.process_definition_id
        )

    @pytest.mark.parametrize(
        ("state", "expected"),
        [
            (ProcessState.CREATED, False),
            (ProcessState.READY, False),
            (ProcessState.RUNNING, True),
            (ProcessState.WAITING, False),
            (ProcessState.BLOCKED, False),
            (ProcessState.COMPLETED, False),
            (ProcessState.FAILED, False),
            (ProcessState.CANCELLED, False),
        ],
    )
    def test_is_running(
        self,
        process_definition,
        state,
        expected,
    ):
        process = Process(definition=process_definition)

        process.state = state

        assert process.is_running is expected

    @pytest.mark.parametrize(
        ("state", "expected"),
        [
            (ProcessState.CREATED, False),
            (ProcessState.READY, True),
            (ProcessState.RUNNING, False),
            (ProcessState.WAITING, False),
            (ProcessState.BLOCKED, False),
            (ProcessState.COMPLETED, False),
            (ProcessState.FAILED, False),
            (ProcessState.CANCELLED, False),
        ],
    )
    def test_is_ready(
        self,
        process_definition,
        state,
        expected,
    ):
        process = Process(definition=process_definition)

        process.state = state

        assert process.is_ready is expected

    @pytest.mark.parametrize(
        ("state", "expected"),
        [
            (ProcessState.CREATED, False),
            (ProcessState.READY, False),
            (ProcessState.RUNNING, False),
            (ProcessState.WAITING, False),
            (ProcessState.BLOCKED, False),
            (ProcessState.COMPLETED, True),
            (ProcessState.FAILED, True),
            (ProcessState.CANCELLED, True),
        ],
    )
    def test_is_finished(
        self,
        process_definition,
        state,
        expected,
    ):
        process = Process(definition=process_definition)

        process.state = state

        assert process.is_finished is expected


# ============================================================================
# Age
# ============================================================================


class TestAge:
    """
    Process.age_seconds should always report a non-negative elapsed time
    since creation.
    """

    def test_age_seconds_is_non_negative(
        self,
        process_definition,
    ):
        process = Process(definition=process_definition)

        assert process.age_seconds >= 0

    def test_age_seconds_returns_float(
        self,
        process_definition,
    ):
        process = Process(definition=process_definition)

        assert isinstance(process.age_seconds, float)


# ============================================================================
# Representation
# ============================================================================


class TestRepresentation:
    """
    repr(Process) should contain enough information to diagnose runtime
    issues from logs without exposing excessive internal state.
    """

    def test_repr_contains_process_id(
        self,
        process_definition,
    ):
        process = Process(definition=process_definition)

        representation = repr(process)

        assert str(process.process_id) in representation

    def test_repr_contains_process_name(
        self,
        process_definition,
    ):
        process = Process(definition=process_definition)

        representation = repr(process)

        assert process.definition.name in representation

    def test_repr_contains_process_state(
        self,
        process_definition,
    ):
        process = Process(definition=process_definition)

        representation = repr(process)

        assert process.state.value in representation


# ============================================================================
# Object Identity
# ============================================================================


class TestIdentity:
    """
    A Process owns a unique runtime identity.

    Multiple Process instances created from the same ProcessDefinition
    should still represent distinct runtime executions.
    """

    def test_processes_share_definition_but_not_identity(
        self,
        process_definition,
    ):
        process1 = Process(definition=process_definition)
        process2 = Process(definition=process_definition)

        assert process1.definition is process2.definition
        assert process1.process_id != process2.process_id

    def test_process_stores_definition_reference(
        self,
        process_definition,
    ):
        process = Process(definition=process_definition)

        assert process.definition is process_definition


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """
    Verify behavior at API boundaries.
    """

    def test_process_accepts_none_goal(
        self,
        process_definition,
    ):
        process = Process(
            definition=process_definition,
            goal_id=None,
        )

        assert process.goal_id is None

    def test_process_accepts_none_parent(
        self,
        process_definition,
    ):
        process = Process(
            definition=process_definition,
            parent_process_id=None,
        )

        assert process.parent_process_id is None

    def test_default_budget_created_per_process(
        self,
        process_definition,
    ):
        """
        Each Process should receive its own ResourceBudget instance.

        Although ResourceBudget is immutable today, this test protects
        against accidental shared mutable defaults in the future.
        """
        process1 = Process(definition=process_definition)
        process2 = Process(definition=process_definition)

        assert process1.budget is not process2.budget