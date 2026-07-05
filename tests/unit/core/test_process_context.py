"""
Tests for emergence.core.process_context.

Architectural Contract
----------------------
ProcessContext is an immutable dependency container provided to every
executing process.

It deliberately exposes only the kernel services a process is allowed
to access, preventing direct coupling to the Kernel itself.

These tests protect the following invariants:

* ProcessContext is immutable.
* Identity information is preserved.
* Kernel service references are preserved.
* Optional GoalID is supported.
* Equality and hashing behave as expected.
"""

from dataclasses import FrozenInstanceError

import pytest

from emergence.core.ids import GoalID, ProcessID
from emergence.core.process_context import ProcessContext
from emergence.core.process_definition import ProcessDefinition
from tests.helpers import build_test_process_context


@pytest.fixture
def process_definition() -> ProcessDefinition:
    return ProcessDefinition(
        name="test",
        implementation="fake",
        version="1.0.0",
    )


# ============================================================================
# Construction
# ============================================================================


class TestConstruction:
    """
    Verify ProcessContext construction.

    These tests ensure the runtime context correctly stores process identity
    and references to kernel services.
    """

    def test_construction_with_goal(
        self,
        process_definition,
    ):
        process_id = ProcessID.new()
        goal_id = GoalID.new()

        context = build_test_process_context(
            process_definition,
            process_id=process_id,
            goal_id=goal_id,
        )

        assert context.process_id == process_id
        assert context.goal_id == goal_id
        assert context.definition is process_definition

    def test_construction_without_goal(
        self,
        process_definition,
    ):
        process_id = ProcessID.new()

        context = build_test_process_context(
            process_definition,
            process_id=process_id,
        )

        assert context.process_id == process_id
        assert context.goal_id is None


# ============================================================================
# Immutability
# ============================================================================


class TestImmutability:
    """
    ProcessContext must remain immutable for the lifetime of a process.

    This prevents accidental replacement of kernel service references or
    identity information during execution.
    """

    def test_process_context_is_immutable(
        self,
        process_definition,
    ):
        context = build_test_process_context(process_definition)

        with pytest.raises(FrozenInstanceError):
            context.process_id = ProcessID.new()


# ============================================================================
# Value Object Behaviour
# ============================================================================


class TestValueObjectBehavior:
    """
    ProcessContext behaves as an immutable dataclass.

    Equality and hashing should depend on all stored fields.
    """

    def test_equal_contexts_compare_equal(
        self,
        process_definition,
        state_store,
        event_bus,
        mailbox_manager,
    ):
        process_id = ProcessID.new()
        goal_id = GoalID.new()

        context1 = build_test_process_context(
            process_definition,
            process_id=process_id,
            goal_id=goal_id,
            event_bus=event_bus,
        )

        context2 = build_test_process_context(
            process_definition,
            process_id=process_id,
            goal_id=goal_id,
            event_bus=event_bus,
        )

        assert context1.process_id == context2.process_id
        assert context1.goal_id == context2.goal_id
        assert context1.definition == context2.definition

    def test_contexts_with_different_process_ids_are_not_equal(
        self,
        process_definition,
    ):
        context1 = build_test_process_context(process_definition)
        context2 = build_test_process_context(process_definition)

        assert context1 != context2

    def test_process_context_is_not_hashable_with_definition(
        self,
        process_definition,
    ):
        context = build_test_process_context(process_definition)

        with pytest.raises(TypeError):
            {context: "running"}
