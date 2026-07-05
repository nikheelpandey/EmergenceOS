from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from emergence.core.budget import ResourceBudget
from emergence.core.ids import ProcessID


@dataclass
class BudgetUsage:
    """Mutable consumption counters for a single process."""

    tokens: int = 0
    tool_invocations: int = 0
    cost_usd: float = 0.0
    execution_seconds: float = 0.0
    retries: int = 0


class BudgetExhaustedError(Exception):
    """Raised when a process has exhausted its resource budget."""


class BudgetTracker:
    """
    Tracks per-process resource consumption against ResourceBudget limits.
    """

    def __init__(self) -> None:
        self._usage: dict[str, BudgetUsage] = {}

    def usage(self, process_id: ProcessID) -> BudgetUsage:
        pid = str(process_id)
        if pid not in self._usage:
            self._usage[pid] = BudgetUsage()
        return self._usage[pid]

    def can_dispatch(
        self,
        process_id: ProcessID,
        budget: ResourceBudget,
    ) -> bool:
        """Return True if the process may be scheduled for execution."""
        usage = self.usage(process_id)

        if usage.tokens >= budget.max_tokens:
            return False
        if usage.tool_invocations >= budget.max_tool_invocations:
            return False
        if usage.cost_usd >= budget.max_cost_usd:
            return False
        if usage.retries > budget.max_retries:
            return False

        return True

    def check_timeout(
        self,
        started_at: datetime | None,
        budget: ResourceBudget,
    ) -> bool:
        """
        Return True if execution time has exceeded the budget limit.
        """
        if started_at is None:
            return False

        elapsed = (datetime.now(UTC) - started_at).total_seconds()
        return elapsed > budget.max_execution_time_seconds

    def record_execution(
        self,
        process_id: ProcessID,
        *,
        tokens: int = 0,
        tool_invocations: int = 0,
        cost_usd: float = 0.0,
        execution_seconds: float = 0.0,
    ) -> None:
        usage = self.usage(process_id)
        usage.tokens += tokens
        usage.tool_invocations += tool_invocations
        usage.cost_usd += cost_usd
        usage.execution_seconds += execution_seconds

    def record_retry(self, process_id: ProcessID) -> None:
        self.usage(process_id).retries += 1

    def clear(self, process_id: ProcessID) -> None:
        self._usage.pop(str(process_id), None)

    def clear_all(self) -> None:
        self._usage.clear()
