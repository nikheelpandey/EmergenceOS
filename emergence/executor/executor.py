"""
executor/executor.py

The Executor is responsible for delegating process execution
to the appropriate Runner.

The Executor does not execute processes itself.

Responsibilities
----------------
- Maintain a registry of Runners.
- Resolve the appropriate Runner for a Process.
- Delegate execution.
- Return the execution result.

Non-Responsibilities
--------------------
- Scheduling
- Process lifecycle management
- Event publishing
- Memory management
- Tool execution
"""

from __future__ import annotations

from typing import Any, Dict

from emergence.core.process import Process
from emergence.executor.runner import Runner


class RunnerAlreadyRegisteredError(Exception):
    """Raised when attempting to register a duplicate Runner."""


class RunnerNotFoundError(Exception):
    """Raised when no Runner exists for a process implementation."""


class Executor:
    """
    Delegates process execution to registered Runners.
    """

    def __init__(self) -> None:
        self._runners: Dict[str, Runner] = {}

    # ------------------------------------------------------------------
    # Runner Registry
    # ------------------------------------------------------------------

    def register_runner(
        self,
        implementation: str,
        runner: Runner,
    ) -> None:
        """
        Register a Runner for an implementation identifier.

        Parameters
        ----------
        implementation:
            Unique implementation name
            (e.g. "python", "ollama", "workflow").

        runner:
            Runner instance.

        Raises
        ------
        RunnerAlreadyRegisteredError
            If the implementation is already registered.
        """
        if implementation in self._runners:
            raise RunnerAlreadyRegisteredError(
                f"Runner already registered for '{implementation}'."
            )

        self._runners[implementation] = runner

    def unregister_runner(self, implementation: str) -> None:
        """
        Remove a Runner registration.

        Removing a non-existent Runner is ignored.
        """
        self._runners.pop(implementation, None)

    def has_runner(self, implementation: str) -> bool:
        """
        Return True if a Runner exists.
        """
        return implementation in self._runners

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, process: Process) -> Any:
        """
        Execute a process using its registered Runner.

        Raises
        ------
        RunnerNotFoundError
            If no Runner is registered for the implementation.
        """
        implementation = process.definition.implementation

        try:
            runner = self._runners[implementation]
        except KeyError as exc:
            raise RunnerNotFoundError(
                f"No Runner registered for '{implementation}'."
            ) from exc

        return runner.run(process)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def registered_implementations(self) -> tuple[str, ...]:
        """
        Return all registered implementation identifiers.
        """
        return tuple(self._runners.keys())

    def clear(self) -> None:
        """
        Remove all registered Runners.

        Primarily useful for tests.
        """
        self._runners.clear()

    def __len__(self) -> int:
        return len(self._runners)