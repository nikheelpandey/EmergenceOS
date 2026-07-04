"""
core/budget.py

Defines immutable resource budgets for EmergenceOS.

A ResourceBudget specifies the maximum resources a Process is permitted
to consume during its lifetime.

Budgets describe limits only.

Actual resource consumption is tracked separately by the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    """
    Immutable execution limits for a Process.

    Attributes
    ----------
    max_tokens:
        Maximum number of LLM tokens the process may consume.

    max_execution_time_seconds:
        Maximum wall-clock execution time.

    max_memory_mb:
        Maximum memory the process may allocate.

    max_tool_invocations:
        Maximum number of tool calls allowed.

    max_cost_usd:
        Maximum monetary cost.

    max_retries:
        Maximum number of retries before the process is considered failed.
    """

    max_tokens: int = 10_000
    max_execution_time_seconds: int = 300
    max_memory_mb: int = 512
    max_tool_invocations: int = 100
    max_cost_usd: float = 1.0
    max_retries: int = 3

    def __post_init__(self) -> None:
        """Validate all resource limits."""

        if self.max_tokens < 0:
            raise ValueError("max_tokens must be non-negative.")

        if self.max_execution_time_seconds <= 0:
            raise ValueError(
                "max_execution_time_seconds must be positive."
            )

        if self.max_memory_mb <= 0:
            raise ValueError("max_memory_mb must be positive.")

        if self.max_tool_invocations < 0:
            raise ValueError(
                "max_tool_invocations must be non-negative."
            )

        if self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be non-negative.")

        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative.")