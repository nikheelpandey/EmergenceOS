"""
scheduler/scheduler.py

Event-driven scheduler for EmergenceOS.

The Scheduler owns the ready queue, waiting registry, and dependency
graph. It subscribes to kernel events to wake processes blocked on
messages, state changes, or timers.
"""

from __future__ import annotations

import heapq
from typing import Callable

from emergence.core.event import Event, EventType
from emergence.core.ids import ProcessID
from emergence.core.wait_condition import WaitCondition
from emergence.events.event_bus import EventBus


class SchedulerEmptyError(Exception):
    """Raised when attempting to dequeue from an empty scheduler."""


WakeCallback = Callable[[ProcessID], None]


class Scheduler:
    """
    Priority scheduler with dependency awareness and event-driven wakeup.

    Processes are ordered by priority (higher first) with FIFO tie-breaking.
    Processes waiting on a WaitCondition are excluded from the ready queue
    until their condition is satisfied.
    """

    WAKE_EVENTS: frozenset[EventType] = frozenset({
        EventType.MESSAGE_RECEIVED,
        EventType.STATE_CREATED,
        EventType.STATE_CHANGED,
        EventType.STATE_DELETED,
        EventType.PROCESS_COMPLETED,
        EventType.PROCESS_FAILED,
        EventType.PROCESS_CANCELLED,
        EventType.ARTIFACT_CREATED,
        EventType.ARTIFACT_UPDATED,
        EventType.ARTIFACT_DELETED,
    })

    def __init__(
        self,
        event_bus: EventBus,
        *,
        on_wake: WakeCallback | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._on_wake = on_wake

        self._queue: list[tuple[int, int, ProcessID]] = []
        self._seq = 0
        self._membership: set[ProcessID] = set()
        self._priorities: dict[ProcessID, int] = {}

        self._waiting: dict[ProcessID, WaitCondition] = {}
        self._pending_deps: dict[ProcessID, set[ProcessID]] = {}

        self._event_bus.subscribe(
            EventType.MESSAGE_RECEIVED,
            self._on_event,
        )
        self._event_bus.subscribe(
            EventType.STATE_CREATED,
            self._on_event,
        )
        self._event_bus.subscribe(
            EventType.STATE_CHANGED,
            self._on_event,
        )
        self._event_bus.subscribe(
            EventType.STATE_DELETED,
            self._on_event,
        )
        self._event_bus.subscribe(
            EventType.PROCESS_COMPLETED,
            self._on_event,
        )
        self._event_bus.subscribe(
            EventType.PROCESS_FAILED,
            self._on_event,
        )
        self._event_bus.subscribe(
            EventType.PROCESS_CANCELLED,
            self._on_event,
        )
        for event_type in (
            EventType.ARTIFACT_CREATED,
            EventType.ARTIFACT_UPDATED,
            EventType.ARTIFACT_DELETED,
        ):
            self._event_bus.subscribe(event_type, self._on_event)

    # ------------------------------------------------------------------
    # Queue Operations
    # ------------------------------------------------------------------

    def enqueue(
        self,
        process_id: ProcessID,
        *,
        priority: int = 0,
        depends_on: tuple[ProcessID, ...] = (),
    ) -> None:
        """
        Add a process to the ready queue or defer until dependencies resolve.
        """
        self._priorities[process_id] = priority

        if depends_on:
            self._pending_deps[process_id] = set(depends_on)
            return

        self._add_to_queue(process_id, priority)

    def dequeue(self) -> ProcessID:
        """
        Remove and return the highest-priority runnable process.

        Raises
        ------
        SchedulerEmptyError
            If the scheduler is empty.
        """
        if not self._queue:
            raise SchedulerEmptyError("Scheduler is empty.")

        _, _, process_id = heapq.heappop(self._queue)
        self._membership.discard(process_id)
        return process_id

    def peek(self) -> ProcessID:
        """Return the next runnable process without removing it."""
        if not self._queue:
            raise SchedulerEmptyError("Scheduler is empty.")
        return self._queue[0][2]

    # ------------------------------------------------------------------
    # Waiting
    # ------------------------------------------------------------------

    def mark_waiting(
        self,
        process_id: ProcessID,
        condition: WaitCondition,
    ) -> None:
        """Register a process as waiting on a condition."""
        self._waiting[process_id] = condition
        self._membership.discard(process_id)
        self._queue = [
            entry for entry in self._queue if entry[2] != process_id
        ]
        heapq.heapify(self._queue)

    def is_waiting(self, process_id: ProcessID) -> bool:
        return process_id in self._waiting

    def evaluate_waiting(self) -> list[ProcessID]:
        """
        Check all waiting processes and wake those whose conditions
        are satisfied.
        """
        woken: list[ProcessID] = []

        for process_id, condition in list(self._waiting.items()):
            if condition.is_satisfied():
                del self._waiting[process_id]
                priority = self._priorities.get(process_id, 0)
                self._add_to_queue(process_id, priority)
                woken.append(process_id)

                if self._on_wake is not None:
                    self._on_wake(process_id)

        return woken

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    def notify_completed(self, process_id: ProcessID) -> list[ProcessID]:
        """
        Notify the scheduler that a process has reached a terminal state.

        Returns process IDs that became ready due to dependency resolution.
        """
        released: list[ProcessID] = []

        for pid, deps in list(self._pending_deps.items()):
            deps.discard(process_id)
            if not deps:
                del self._pending_deps[pid]
                priority = self._priorities.get(pid, 0)
                self._add_to_queue(pid, priority)
                released.append(pid)

        return released

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def is_empty(self) -> bool:
        """Return True if there are no runnable processes."""
        return not self._queue

    def contains(self, process_id: ProcessID) -> bool:
        return process_id in self._membership

    def queued_ids(self) -> tuple[ProcessID, ...]:
        return tuple(entry[2] for entry in sorted(self._queue))

    def waiting_ids(self) -> tuple[ProcessID, ...]:
        return tuple(self._waiting.keys())

    def pending_dependency_ids(self) -> tuple[ProcessID, ...]:
        return tuple(self._pending_deps.keys())

    def clear(self) -> None:
        self._queue.clear()
        self._membership.clear()
        self._priorities.clear()
        self._waiting.clear()
        self._pending_deps.clear()
        self._seq = 0

    def __len__(self) -> int:
        return len(self._queue)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _add_to_queue(self, process_id: ProcessID, priority: int) -> None:
        if process_id in self._membership:
            return
        if process_id in self._waiting:
            return

        self._seq += 1
        heapq.heappush(
            self._queue,
            (-priority, self._seq, process_id),
        )
        self._membership.add(process_id)

    def _on_event(self, event: Event) -> None:
        self.evaluate_waiting()

        if event.event_type in {
            EventType.PROCESS_COMPLETED,
            EventType.PROCESS_FAILED,
            EventType.PROCESS_CANCELLED,
        }:
            source = event.source_process
            if source is not None:
                self.notify_completed(source)
