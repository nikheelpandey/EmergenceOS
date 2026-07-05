"""
Tests for emergenceos.core.budget.

Architectural Contract
----------------------
A ResourceBudget defines immutable execution limits for a Process.

These tests protect the following invariants:

* Budgets are immutable value objects.
* Default values remain stable.
* Valid custom budgets can be created.
* Every resource limit is validated independently.
* Invalid resource limits fail fast.
"""

from dataclasses import FrozenInstanceError

import pytest

from emergence.core.budget import ResourceBudget


# ============================================================================
# Construction
# ============================================================================


class TestConstruction:
    """
    Verify ResourceBudget construction.

    These tests ensure that valid budgets can always be created and that
    default values remain stable over time.
    """

    def test_default_budget_values(self):
        budget = ResourceBudget()

        assert budget.max_tokens == 10_000
        assert budget.max_execution_time_seconds == 300
        assert budget.max_memory_mb == 512
        assert budget.max_tool_invocations == 100
        assert budget.max_cost_usd == 1.0
        assert budget.max_retries == 3

    def test_custom_budget_values(self):
        budget = ResourceBudget(
            max_tokens=50_000,
            max_execution_time_seconds=600,
            max_memory_mb=2048,
            max_tool_invocations=250,
            max_cost_usd=25.5,
            max_retries=10,
        )

        assert budget.max_tokens == 50_000
        assert budget.max_execution_time_seconds == 600
        assert budget.max_memory_mb == 2048
        assert budget.max_tool_invocations == 250
        assert budget.max_cost_usd == 25.5
        assert budget.max_retries == 10


# ============================================================================
# Immutability
# ============================================================================


class TestImmutability:
    """
    ResourceBudget is an immutable value object.

    Once created, resource limits must never change.
    """

    def test_budget_is_immutable(self):
        budget = ResourceBudget()

        with pytest.raises(FrozenInstanceError):
            budget.max_tokens = 99999


# ============================================================================
# Equality & Hashing
# ============================================================================


class TestValueObjectBehavior:
    """
    Budgets should behave like immutable value objects.

    Equal budgets should compare equal and have identical hashes.
    """

    def test_equal_budgets_compare_equal(self):
        budget1 = ResourceBudget()
        budget2 = ResourceBudget()

        assert budget1 == budget2

    def test_equal_budgets_have_same_hash(self):
        budget1 = ResourceBudget()
        budget2 = ResourceBudget()

        assert hash(budget1) == hash(budget2)

    def test_different_budgets_are_not_equal(self):
        budget1 = ResourceBudget()
        budget2 = ResourceBudget(max_tokens=20_000)

        assert budget1 != budget2


# ============================================================================
# Validation
# ============================================================================


class TestValidation:
    """
    Every resource limit should be validated independently.

    Invalid values must fail immediately rather than allowing invalid process
    budgets to enter the kernel.
    """

    def test_negative_max_tokens_raises(self):
        with pytest.raises(
            ValueError,
            match="max_tokens must be non-negative.",
        ):
            ResourceBudget(max_tokens=-1)

    def test_zero_execution_time_raises(self):
        with pytest.raises(
            ValueError,
            match="max_execution_time_seconds must be positive.",
        ):
            ResourceBudget(max_execution_time_seconds=0)

    def test_negative_execution_time_raises(self):
        with pytest.raises(
            ValueError,
            match="max_execution_time_seconds must be positive.",
        ):
            ResourceBudget(max_execution_time_seconds=-10)

    def test_zero_memory_raises(self):
        with pytest.raises(
            ValueError,
            match="max_memory_mb must be positive.",
        ):
            ResourceBudget(max_memory_mb=0)

    def test_negative_memory_raises(self):
        with pytest.raises(
            ValueError,
            match="max_memory_mb must be positive.",
        ):
            ResourceBudget(max_memory_mb=-512)

    def test_negative_tool_invocations_raises(self):
        with pytest.raises(
            ValueError,
            match="max_tool_invocations must be non-negative.",
        ):
            ResourceBudget(max_tool_invocations=-1)

    def test_negative_cost_raises(self):
        with pytest.raises(
            ValueError,
            match="max_cost_usd must be non-negative.",
        ):
            ResourceBudget(max_cost_usd=-0.01)

    def test_negative_retries_raises(self):
        with pytest.raises(
            ValueError,
            match="max_retries must be non-negative.",
        ):
            ResourceBudget(max_retries=-1)


# ============================================================================
# Boundary Conditions
# ============================================================================


class TestBoundaryConditions:
    """
    Verify the boundary values accepted by the validator.

    These tests document the exact limits accepted by the ResourceBudget.
    """

    def test_zero_tokens_allowed(self):
        budget = ResourceBudget(max_tokens=0)

        assert budget.max_tokens == 0

    def test_zero_tool_invocations_allowed(self):
        budget = ResourceBudget(max_tool_invocations=0)

        assert budget.max_tool_invocations == 0

    def test_zero_cost_allowed(self):
        budget = ResourceBudget(max_cost_usd=0.0)

        assert budget.max_cost_usd == 0.0

    def test_zero_retries_allowed(self):
        budget = ResourceBudget(max_retries=0)

        assert budget.max_retries == 0

    def test_minimum_positive_execution_time_allowed(self):
        budget = ResourceBudget(max_execution_time_seconds=1)

        assert budget.max_execution_time_seconds == 1

    def test_minimum_positive_memory_allowed(self):
        budget = ResourceBudget(max_memory_mb=1)

        assert budget.max_memory_mb == 1