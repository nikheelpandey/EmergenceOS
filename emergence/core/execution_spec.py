from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ExecutionSpec:
    """
    Describes how a process should be executed.

    Separates the runner backend from the execution target,
    enabling runner replacement without kernel changes.
    """

    runner: str
    target: str
    config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.runner.strip():
            raise ValueError("ExecutionSpec.runner cannot be empty.")
        if not self.target.strip():
            raise ValueError("ExecutionSpec.target cannot be empty.")

    @property
    def registry_key(self) -> str:
        """Key used to resolve the runner in the Executor."""
        return f"{self.runner}:{self.target}"
