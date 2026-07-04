"""
kernel/kernel.py

The EmergenceOS Kernel.

The Kernel is responsible for coordinating the execution of processes.
It owns the process lifecycle but delegates scheduling and execution
to specialized subsystems.

Responsibilities
----------------
- Spawn processes
- Register processes
- Schedule processes
- Execute scheduled processes
- Manage process lifecycle
- Publish lifecycle events

Non-Responsibilities
--------------------
- Planning
- Tool execution
- Memory management
- Checkpointing
- LLM inference
- Scheduling policy
"""

from __future__ import annotations

from typing import Optional

from emergence.core.event import Event, EventType
from emergence.core.ids import GoalID, ProcessID
from emergence.core.process import Process
from emergence.core.process_definition import ProcessDefinition
from emergence.core.state import ProcessState
from emergence.events.event_bus import EventBus
from emergence.executor.executor import Executor
from emergence.kernel.process_table import ProcessTable
from emergence.scheduler.scheduler import Scheduler, SchedulerEmptyError


class Kernel:
    """
    The central coordinator of EmergenceOS.

    The Kernel owns process lifecycle management while delegating
    scheduling and execution to dedicated subsystems.
    """

    def __init__(
        self,
        event_bus: EventBus,
        process_table: ProcessTable,
        scheduler: Scheduler,
        executor: Executor,
    ) -> None:
        self._event_bus = event_bus
        self._process_table = process_table
        self._scheduler = scheduler
        self._executor = executor

    # ------------------------------------------------------------------
    # Process Creation
    # ------------------------------------------------------------------

    def spawn(
        self,
        definition: ProcessDefinition,
        goal_id: GoalID | None = None,
        parent_process_id: ProcessID | None = None,
    ) -> Process:
        """
        Create and schedule a new process.
        """

        process = Process(
            definition=definition,
            goal_id=goal_id,
            parent_process_id=parent_process_id,
        )

        # CREATED -> READY
        process.transition_to(ProcessState.READY)

        self._process_table.add(process)

        self._scheduler.enqueue(process.process_id)

        self._publish_event(
            EventType.PROCESS_CREATED,
            process,
        )

        self._publish_event(
            EventType.PROCESS_READY,
            process,
        )

        return process

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_next(self) -> Process | None:
        """
        Execute the next scheduled process.

        Returns
        -------
        Process | None
            The executed process or None if the scheduler is empty.
        """
        print("run_next() entered")

        try:
            process_id = self._scheduler.dequeue()
            print("Dequeued:", process_id)
        except SchedulerEmptyError:
            return None

        process = self._process_table.get(process_id)
        print("Retrieved:", process)

        # try:
        process.start()

        self._publish_event(
            EventType.PROCESS_STARTED,
            process,
        )
        print("Calling executor")
        self._executor.execute(process)
        print("Executor returned")

        process.complete()

        self._publish_event(
            EventType.PROCESS_COMPLETED,
            process,
        )

        # except Exception as exc:

        #     try:
        #         process.fail(str(exc))
        #     finally:
        #         self._publish_event(
        #             EventType.PROCESS_FAILED,
        #             process,
        #             {
        #                 "error": str(exc),
        #             },
        #         )

        return process

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def get_process(
        self,
        process_id: ProcessID,
    ) -> Process:
        """
        Retrieve a process by ID.
        """
        return self._process_table.get(process_id)

    def process_exists(
        self,
        process_id: ProcessID,
    ) -> bool:
        """
        Return True if a process exists.
        """
        return self._process_table.exists(process_id)

    def process_count(self) -> int:
        """
        Return the number of live processes.
        """
        return len(self._process_table)

    def has_work(self) -> bool:
        """
        Return True if runnable processes exist.
        """
        return not self._scheduler.is_empty()

    def run(self) -> None:
        print("Kernel.run() entered")

        while self.has_work():
            print("Kernel has work")
            self.run_next()

        print("Kernel.run() exiting")

        # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _publish_event(
        self,
        event_type: EventType,
        process: Process,
        payload: dict | None = None,
    ) -> None:
        """
        Publish a lifecycle event.
        """

        event = Event(
            event_type=event_type,
            source_process=process.process_id,
            payload=payload or {},
        )

        self._event_bus.publish(event)