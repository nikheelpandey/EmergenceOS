"""
scheduler/scheduler.py

A simple FIFO scheduler for EmergenceOS.

The Scheduler owns the ready queue of processes awaiting execution.
It does not own Process objects themselves, only their ProcessIDs.
"""

from __future__ import annotations

from collections import deque
from typing import Deque

from emergence.core.ids import ProcessID


class SchedulerEmptyError(Exception):
    """Raised when attempting to dequeue from an empty scheduler."""


class Scheduler:
    """
    A deterministic FIFO scheduler.

    The Scheduler maintains a queue of ProcessIDs representing
    runnable processes.
    """

    def __init__(self) -> None:
        self._queue: Deque[ProcessID] = deque()
        self._membership: set[ProcessID] = set()

    # ------------------------------------------------------------------
    # Queue Operations
    # ------------------------------------------------------------------

    def enqueue(self, process_id: ProcessID) -> None:
        """
        Add a process to the ready queue.

        Duplicate entries are ignored.
        """
        if process_id in self._membership:
            return

        self._queue.append(process_id)
        self._membership.add(process_id)

    def dequeue(self) -> ProcessID:
        """
        Remove and return the next runnable process.

        Raises
        ------
        SchedulerEmptyError
            If the scheduler is empty.
        """
        if not self._queue:
            raise SchedulerEmptyError("Scheduler is empty.")

        process_id = self._queue.popleft()
        self._membership.remove(process_id)
        return process_id

    def peek(self) -> ProcessID:
        """
        Return the next runnable process without removing it.

        Raises
        ------
        SchedulerEmptyError
            If the scheduler is empty.
        """
        if not self._queue:
            raise SchedulerEmptyError("Scheduler is empty.")

        return self._queue[0]

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def is_empty(self) -> bool:
        """Return True if there are no runnable processes."""
        return not self._queue

    def contains(self, process_id: ProcessID) -> bool:
        """Return True if the process is already scheduled."""
        return process_id in self._membership

    # ------------------------------------------------------------------
    # Collection Protocol
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._queue)

    def clear(self) -> None:
        """Remove all scheduled processes."""
        self._queue.clear()
        self._membership.clear()