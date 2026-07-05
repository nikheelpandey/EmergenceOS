"""
Tests for emergence.core.budget_tracker.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from emergence.core.budget import ResourceBudget
from emergence.core.budget_tracker import BudgetTracker
from emergence.core.ids import ProcessID


class TestBudgetTracker:
    def test_can_dispatch_within_limits(self):
        tracker = BudgetTracker()
        pid = ProcessID.new()
        budget = ResourceBudget()

        assert tracker.can_dispatch(pid, budget) is True

    def test_cannot_dispatch_when_tokens_exhausted(self):
        tracker = BudgetTracker()
        pid = ProcessID.new()
        budget = ResourceBudget(max_tokens=100)

        tracker.record_execution(pid, tokens=100)

        assert tracker.can_dispatch(pid, budget) is False

    def test_check_timeout_detects_exceeded_time(self):
        tracker = BudgetTracker()
        budget = ResourceBudget(max_execution_time_seconds=1)
        started = datetime.now(UTC) - timedelta(seconds=5)

        assert tracker.check_timeout(started, budget) is True

    def test_check_timeout_within_limit(self):
        tracker = BudgetTracker()
        budget = ResourceBudget(max_execution_time_seconds=300)
        started = datetime.now(UTC)

        assert tracker.check_timeout(started, budget) is False

    def test_record_execution_accumulates(self):
        tracker = BudgetTracker()
        pid = ProcessID.new()

        tracker.record_execution(pid, tokens=50, tool_invocations=2)
        tracker.record_execution(pid, tokens=30)

        usage = tracker.usage(pid)
        assert usage.tokens == 80
        assert usage.tool_invocations == 2

    def test_clear_removes_usage(self):
        tracker = BudgetTracker()
        pid = ProcessID.new()

        tracker.record_execution(pid, tokens=10)
        tracker.clear(pid)

        assert tracker.usage(pid).tokens == 0
