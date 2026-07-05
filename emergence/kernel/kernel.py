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
- Enforce resource budgets
- Wake waiting processes

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

from datetime import UTC, datetime
from uuid import UUID, uuid4

from emergence.core.budget_tracker import BudgetExhaustedError
from emergence.core.event import Event, EventType
from emergence.cognitive.manager import CognitiveManager, TaskSpec
from emergence.core.goal import Goal
from emergence.core.ids import EventID, GoalID, PlanID, ProcessID
from emergence.core.plan import Plan
from emergence.core.process import Process
from emergence.core.process_context import ProcessContext
from emergence.core.process_definition import ProcessDefinition
from emergence.core.process_waiting import ProcessWaiting
from emergence.core.state import ProcessState
from emergence.executor.executor import Executor
from emergence.kernel.context import KernelContext
from emergence.kernel.lifecycle import LifecycleManager
from emergence.scheduler.scheduler import SchedulerEmptyError
from emergence.security.capabilities import capabilities_for_definition
from emergence.security.errors import PermissionDeniedError
from emergence.security.gated_checkpoint_manager import (
    GatedCheckpointManager,
)
from emergence.security.gated_event_bus import GatedEventBus
from emergence.security.gated_mailbox_manager import GatedMailboxManager
from emergence.security.gated_memory_manager import GatedMemoryManager
from emergence.security.gated_state_store import GatedStateStore
from emergence.security.gated_tool_access import GatedToolAccess


class Kernel:
    """
    The central coordinator of EmergenceOS.

    The Kernel owns process lifecycle management while delegating
    scheduling and execution to dedicated subsystems.
    """

    def __init__(
        self,
        ctx: KernelContext,
        executor: Executor,
        lifecycle: LifecycleManager | None = None,
    ) -> None:
        self._ctx = ctx
        self._executor = executor
        self._lifecycle = lifecycle or LifecycleManager()

        self._ctx.scheduler._on_wake = self._wake_process  # noqa: SLF001

    # ------------------------------------------------------------------
    # Process Creation
    # ------------------------------------------------------------------

    def spawn(
        self,
        definition: ProcessDefinition,
        goal_id: GoalID | None = None,
        parent_process_id: ProcessID | None = None,
        *,
        priority: int = 0,
        depends_on: tuple[ProcessID, ...] = (),
        causation_id: EventID | None = None,
        correlation_id: UUID | None = None,
    ) -> Process:
        """
        Create and schedule a new process.
        """

        if not self._ctx.registry.exists(definition.name):
            self._ctx.registry.register(definition)

        process = Process(
            definition=definition,
            goal_id=goal_id,
            parent_process_id=parent_process_id,
            budget=definition.default_budget,
        )

        pid = str(process.process_id)

        self._ctx.mailboxes.create(pid)

        for capability in capabilities_for_definition(definition):
            self._ctx.capabilities.grant(pid, capability)

        self._lifecycle.ready(process)

        self._ctx.process_table.add(process)

        self._ctx.scheduler.enqueue(
            process.process_id,
            priority=priority,
            depends_on=depends_on,
        )

        if correlation_id is None:
            correlation_id = uuid4()

        created = self._publish_event(
            EventType.PROCESS_CREATED,
            process,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )

        self._publish_event(
            EventType.PROCESS_READY,
            process,
            correlation_id=correlation_id,
            causation_id=created.event_id,
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
        self._ctx.scheduler.evaluate_waiting()

        try:
            process_id = self._ctx.scheduler.dequeue()
        except SchedulerEmptyError:
            return None

        process = self._ctx.process_table.get(process_id)

        if not self._ctx.budgets.can_dispatch(
            process.process_id,
            process.budget,
        ):
            self._fail_process(
                process,
                "Resource budget exhausted before dispatch.",
            )
            return process

        try:
            self._lifecycle.start(process)

            started = self._publish_event(
                EventType.PROCESS_STARTED,
                process,
            )

            context = self._build_context(process)

            start_time = datetime.now(UTC)
            self._executor.execute(context)
            elapsed = (datetime.now(UTC) - start_time).total_seconds()

            self._ctx.budgets.record_execution(
                process.process_id,
                execution_seconds=elapsed,
            )

            if self._ctx.budgets.check_timeout(
                process.started_at,
                process.budget,
            ):
                self._fail_process(
                    process,
                    "Execution time budget exceeded.",
                )
                return process

            self._lifecycle.complete(process)

            self._publish_event(
                EventType.PROCESS_COMPLETED,
                process,
                causation_id=started.event_id,
                correlation_id=started.correlation_id,
            )

            self._ctx.cognitive.on_process_completed(
                process.process_id,
                self,
            )

        except ProcessWaiting as waiting:
            self._ctx.checkpoints.create_checkpoint(
                process,
                event_offset=self._ctx.event_store.count(),
            )
            self._lifecycle.wait(process)
            self._ctx.scheduler.mark_waiting(
                process.process_id,
                waiting.condition,
            )
            self._publish_event(
                EventType.PROCESS_WAITING,
                process,
            )
            return process

        except PermissionDeniedError as exc:
            self._fail_process(process, str(exc))
            return process

        except Exception as exc:
            self._fail_process(process, str(exc))
            return process

        self._cleanup_process(process)

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
        return self._ctx.process_table.get(process_id)

    def process_exists(
        self,
        process_id: ProcessID,
    ) -> bool:
        """
        Return True if a process exists.
        """
        return self._ctx.process_table.exists(process_id)

    def process_count(self) -> int:
        """
        Return the number of live processes.
        """
        return len(self._ctx.process_table)

    def has_work(self) -> bool:
        """
        Return True if runnable processes exist or waiting processes
        may become runnable.
        """
        if not self._ctx.scheduler.is_empty():
            return True

        self._ctx.scheduler.evaluate_waiting()

        if not self._ctx.scheduler.is_empty():
            return True

        # Wake any waiting process that has pending mailbox messages
        for process in self._ctx.process_table.all():
            if process.state != ProcessState.WAITING:
                continue
            pid = str(process.process_id)
            if self._ctx.mailboxes.pending(pid) > 0:
                self._ctx.scheduler.evaluate_waiting()
                if not self._ctx.scheduler.is_empty():
                    return True

        return False

    def run(self) -> None:
        while self.has_work():
            self.run_next()

    # ------------------------------------------------------------------
    # Cognitive API (M12)
    # ------------------------------------------------------------------

    def create_goal(self, description: str) -> Goal:
        """Create a new goal."""
        return self._ctx.cognitive.create_goal(description)

    def start_planning(self, goal_id: GoalID) -> Goal:
        """Transition a goal to PLANNING state."""
        return self._ctx.cognitive.start_planning(goal_id)

    def create_plan(
        self,
        goal_id: GoalID,
        task_specs: list[TaskSpec],
        *,
        priority: int = 0,
    ) -> Plan:
        """Decompose a goal into a plan with tasks."""
        return self._ctx.cognitive.create_plan(
            goal_id,
            task_specs,
            priority=priority,
        )

    def execute_plan(self, plan_id: PlanID) -> None:
        """Spawn and schedule processes for plan tasks."""
        self._ctx.cognitive.execute_plan(self, plan_id)

    @property
    def context(self) -> KernelContext:
        """Return the kernel service container."""
        return self._ctx

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _wake_process(self, process_id: ProcessID) -> None:
        process = self._ctx.process_table.get(process_id)

        if process.state not in (
            ProcessState.WAITING,
            ProcessState.BLOCKED,
        ):
            return

        self._lifecycle.wake(process)

        self._publish_event(
            EventType.PROCESS_READY,
            process,
        )

    def _build_context(self, process: Process) -> ProcessContext:
        pid = str(process.process_id)

        return ProcessContext(
            process_id=process.process_id,
            goal_id=process.goal_id,
            definition=process.definition,
            state=GatedStateStore(
                self._ctx.state,
                self._ctx.security,
                pid,
            ),
            memory=GatedMemoryManager(
                self._ctx.memory,
                self._ctx.security,
                process.process_id,
            ),
            event_bus=GatedEventBus(
                self._ctx.event_bus,
                self._ctx.security,
                pid,
            ),
            mailboxes=GatedMailboxManager(
                self._ctx.mailboxes,
                self._ctx.security,
                pid,
            ),
            checkpoints=GatedCheckpointManager(
                self._ctx.checkpoints,
                self._ctx.security,
                process.process_id,
                self._ctx.process_table.get,
            ),
            tools=GatedToolAccess(
                self._ctx.tools,
                self._ctx.security,
                process.process_id,
            ),
            _mailbox_manager=self._ctx.mailboxes,
        )

    def _fail_process(self, process: Process, reason: str) -> None:
        try:
            self._lifecycle.fail(process, reason)
        finally:
            self._publish_event(
                EventType.PROCESS_FAILED,
                process,
                {"error": reason},
            )
            self._ctx.cognitive.on_process_failed(process.process_id)

        self._cleanup_process(process)

    def _cleanup_process(self, process: Process) -> None:
        if not process.is_finished:
            return

        pid = str(process.process_id)
        self._ctx.capabilities.clear(pid)
        self._ctx.mailboxes.delete(pid)
        self._ctx.budgets.clear(process.process_id)

    def _publish_event(
        self,
        event_type: EventType,
        process: Process,
        payload: dict | None = None,
        *,
        correlation_id: UUID | None = None,
        causation_id: EventID | None = None,
    ) -> Event:
        """
        Publish a lifecycle event.
        """

        event = Event(
            event_type=event_type,
            source_process=process.process_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload=payload or {},
        )

        self._ctx.event_bus.publish(event)
        return event
