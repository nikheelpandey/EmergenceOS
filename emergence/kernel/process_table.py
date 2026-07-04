"""
kernel/process_table.py

The ProcessTable is the authoritative owner of all live processes
within the EmergenceOS kernel.

It is intentionally simple.

Responsibilities
----------------
- Register processes
- Remove processes
- Lookup processes
- Iterate over processes

Non-Responsibilities
--------------------
- Scheduling
- Execution
- Lifecycle management
- Event publishing
"""

from __future__ import annotations

from typing import Dict, Iterator

from emergence.core.ids import ProcessID
from emergence.core.process import Process


class ProcessAlreadyExistsError(Exception):
    """Raised when attempting to register an existing process."""


class ProcessNotFoundError(Exception):
    """Raised when a process cannot be found."""


class ProcessTable:
    """
    Owns every live Process in the system.

    The ProcessTable is the single source of truth for runtime
    process instances.
    """

    def __init__(self) -> None:
        self._processes: Dict[ProcessID, Process] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def add(self, process: Process) -> None:
        """
        Register a new process.

        Raises
        ------
        ProcessAlreadyExistsError
            If the ProcessID already exists.
        """
        if process.process_id in self._processes:
            raise ProcessAlreadyExistsError(
                f"Process {process.process_id} already exists."
            )

        self._processes[process.process_id] = process

    def remove(self, process_id: ProcessID) -> Process:
        """
        Remove and return a process.

        Raises
        ------
        ProcessNotFoundError
            If the process does not exist.
        """
        try:
            return self._processes.pop(process_id)
        except KeyError as exc:
            raise ProcessNotFoundError(
                f"Unknown process: {process_id}"
            ) from exc

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, process_id: ProcessID) -> Process:
        """
        Retrieve a process by ID.

        Raises
        ------
        ProcessNotFoundError
            If the process does not exist.
        """
        try:
            return self._processes[process_id]
        except KeyError as exc:
            raise ProcessNotFoundError(
                f"Unknown process: {process_id}"
            ) from exc

    def exists(self, process_id: ProcessID) -> bool:
        """
        Return True if the process exists.
        """
        return process_id in self._processes

    # ------------------------------------------------------------------
    # Iteration
    # ------------------------------------------------------------------

    def all(self) -> tuple[Process, ...]:
        """
        Return an immutable snapshot of all live processes.
        """
        return tuple(self._processes.values())

    def ids(self) -> tuple[ProcessID, ...]:
        """
        Return an immutable snapshot of all ProcessIDs.
        """
        return tuple(self._processes.keys())

    # ------------------------------------------------------------------
    # Collection Protocol
    # ------------------------------------------------------------------

    def __contains__(self, process_id: ProcessID) -> bool:
        return process_id in self._processes

    def __len__(self) -> int:
        return len(self._processes)

    def __iter__(self) -> Iterator[Process]:
        return iter(self._processes.values())

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """
        Remove every process.

        Primarily useful for testing.
        """
        self._processes.clear()