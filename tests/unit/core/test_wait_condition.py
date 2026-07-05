"""
Tests for emergence.core.wait_condition.

Architectural Contract
----------------------
WaitCondition is the abstract base for conditions that block a process
until the scheduler determines execution may resume.

These tests protect the following invariants:

* WaitCondition cannot be instantiated directly.
* Concrete subclasses must implement is_satisfied().
* is_satisfied() returns a boolean result.
"""

from __future__ import annotations

import pytest

from emergence.core.wait_condition import WaitCondition


# ============================================================================
# Abstract Base Contract
# ============================================================================


class TestAbstractContract:
    """
    WaitCondition defines the interface for scheduler-driven blocking.
    """

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            WaitCondition()  # type: ignore[abstract]

    def test_subclass_without_is_satisfied_cannot_be_instantiated(self):
        class IncompleteCondition(WaitCondition):
            pass

        with pytest.raises(TypeError):
            IncompleteCondition()  # type: ignore[abstract]


# ============================================================================
# Concrete Implementations
# ============================================================================


class TestConcreteImplementations:
    """
    Concrete wait conditions expose a boolean satisfaction predicate.
    """

    def test_is_satisfied_returns_true(self):
        class AlwaysSatisfied(WaitCondition):
            def is_satisfied(self) -> bool:
                return True

        condition = AlwaysSatisfied()

        assert condition.is_satisfied() is True

    def test_is_satisfied_returns_false(self):
        class NeverSatisfied(WaitCondition):
            def is_satisfied(self) -> bool:
                return False

        condition = NeverSatisfied()

        assert condition.is_satisfied() is False

    def test_is_satisfied_can_change_over_time(self):
        class CounterCondition(WaitCondition):
            def __init__(self, threshold: int) -> None:
                self._count = 0
                self._threshold = threshold

            def is_satisfied(self) -> bool:
                self._count += 1
                return self._count >= self._threshold

        condition = CounterCondition(threshold=3)

        assert condition.is_satisfied() is False
        assert condition.is_satisfied() is False
        assert condition.is_satisfied() is True

    def test_multiple_subclasses_are_independent(self):
        class MessageReceived(WaitCondition):
            def __init__(self, has_message: bool) -> None:
                self._has_message = has_message

            def is_satisfied(self) -> bool:
                return self._has_message

        class StateAvailable(WaitCondition):
            def __init__(self, key: str, store: dict[str, object]) -> None:
                self._key = key
                self._store = store

            def is_satisfied(self) -> bool:
                return self._key in self._store

        message_condition = MessageReceived(has_message=False)
        state_condition = StateAvailable("result", {})

        assert message_condition.is_satisfied() is False
        assert state_condition.is_satisfied() is False
