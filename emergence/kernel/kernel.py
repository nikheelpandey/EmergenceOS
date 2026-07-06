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

import signal
import threading
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

from emergence.core.budget import ResourceBudget
from emergence.core.budget_tracker import BudgetExhaustedError
from emergence.core.event import Event, EventType
from emergence.cognitive.manager import CognitiveManager, TaskSpec
from emergence.cognitive.goal_registry import GoalKind
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
        self._running = False

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
        budget: ResourceBudget | None = None,
    ) -> Process:
        """
        Create and schedule a new process.
        """

        if not self._ctx.registry.exists(definition.name):
            self._ctx.registry.register(definition)

        process_budget = budget
        if process_budget is None and goal_id is not None:
            process_budget = self._ctx.goal_registry.budget_for_goal(goal_id)
        if process_budget is None:
            process_budget = definition.default_budget

        process = Process(
            definition=definition,
            goal_id=goal_id,
            parent_process_id=parent_process_id,
            budget=process_budget,
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

        if goal_id is not None:
            self._ctx.goal_registry.associate_process(
                goal_id,
                process.process_id,
                as_root=parent_process_id is None,
            )

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
        """Drain all runnable work and return (batch mode)."""
        while self.has_work():
            self.run_next()

    def run_forever(
        self,
        *,
        poll_interval: float = 0.05,
    ) -> None:
        """
        Run the kernel until shutdown is requested.

        Unlike ``run()``, the kernel stays alive when idle so
        platform services in WAITING and external ingress can
        wake processes. Terminates on SIGINT/SIGTERM or
        ``shutdown()``.
        """
        self._running = True
        on_main = threading.current_thread() is threading.main_thread()
        previous_sigint = None
        previous_sigterm = None

        def _handle_signal(_signum: int, _frame: object) -> None:
            self._running = False

        if on_main:
            previous_sigint = signal.getsignal(signal.SIGINT)
            previous_sigterm = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGINT, _handle_signal)
            signal.signal(signal.SIGTERM, _handle_signal)

        try:
            while self._running:
                self.tick()
                if self.has_work():
                    self.run_next()
                else:
                    time.sleep(poll_interval)
        finally:
            if on_main and previous_sigint is not None:
                signal.signal(signal.SIGINT, previous_sigint)
                signal.signal(signal.SIGTERM, previous_sigterm)
            self._publish_shutdown()

    def tick(self) -> None:
        """
        Evaluate waiting conditions and timer wakeups.

        Called automatically by ``run_forever`` on each idle cycle.
        """
        self._ctx.scheduler.evaluate_waiting()
        self._ctx.schedule_manager.process_due(self)

        for process in self._ctx.process_table.all():
            if process.state != ProcessState.WAITING:
                continue
            pid = str(process.process_id)
            if self._ctx.mailboxes.pending(pid) > 0:
                self._ctx.scheduler.evaluate_waiting()
                break

    def shutdown(self) -> None:
        """Request graceful shutdown of ``run_forever``."""
        self._running = False

    @property
    def is_running(self) -> bool:
        """Return True while ``run_forever`` is active."""
        return self._running

    def live_process_count(self) -> int:
        """Return processes that have not reached a terminal state."""
        return sum(
            1
            for process in self._ctx.process_table.all()
            if not process.is_finished
        )

    # ------------------------------------------------------------------
    # Cognitive API (M12)
    # ------------------------------------------------------------------

    def create_goal(
        self,
        description: str,
        *,
        kind: GoalKind = GoalKind.ONE_SHOT,
    ) -> Goal:
        """Create a new goal and register it as a living workload."""
        goal = self._ctx.cognitive.create_goal(description)
        self._ctx.goal_registry.register(
            goal.goal_id,
            description,
            kind=kind,
        )
        return goal

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

    def spawn_planner_for_goal(self, goal_id: GoalID) -> Process:
        """
        Spawn the planner plugin to decompose a goal into task specs.

        The planner reads ``planning_goal`` from state and writes
        ``plan_artifact`` when complete.
        """
        goal = self._ctx.cognitive.get_goal(goal_id)
        self._ctx.state.set("planning_goal", goal.description)
        self._ctx.state.set("planning_goal_id", str(goal_id))
        return self.spawn(
            self._ctx.registry.get("planner"),
            goal_id=goal_id,
            priority=10,
        )

    def finalize_plan_from_planner(self, goal_id: GoalID) -> Plan:
        """
        Create a plan from the planner's ``plan_artifact`` in state.
        """
        import json

        raw = self._ctx.state.get("plan_artifact")
        if raw is None:
            raise RuntimeError(
                "plan_artifact not found — planner may not have completed."
            )

        specs_data = json.loads(raw) if isinstance(raw, str) else raw
        task_specs = [
            TaskSpec(
                name=s["name"],
                process_definition_name=s["process_definition_name"],
                dependencies=tuple(s.get("dependencies", [])),
                priority=int(s.get("priority", 0)),
                expected_output=s.get("expected_output", ""),
            )
            for s in specs_data
        ]
        return self.create_plan(goal_id, task_specs)

    def create_plan_from_goal(self, description: str) -> tuple[Goal, Plan]:
        """
        End-to-end: create goal, run planner, finalize plan.

        Runs the kernel until the planner completes, then creates
        the plan from the planner artifact.
        """
        goal = self.create_goal(description)
        self.start_planning(goal.goal_id)
        self.spawn_planner_for_goal(goal.goal_id)
        self.run()
        plan = self.finalize_plan_from_planner(goal.goal_id)
        return goal, plan

    def cancel_goal_processes(self, goal_id: GoalID) -> list[str]:
        """Cancel all non-finished processes associated with a goal."""
        record = self._ctx.goal_registry.get(goal_id)
        if record is None:
            return []

        cancelled: list[str] = []
        for pid in list(record.all_process_ids):
            process_id = ProcessID.from_string(pid)
            if not self._ctx.process_table.exists(process_id):
                continue
            process = self._ctx.process_table.get(process_id)
            if process.is_finished:
                continue
            try:
                self._lifecycle.cancel(process)
            except ValueError:
                try:
                    self._lifecycle.fail(process, "cancelled")
                except ValueError:
                    continue
            self._publish_event(
                EventType.PROCESS_CANCELLED,
                process,
                {"reason": "goal management"},
            )
            self._cleanup_process(process)
            cancelled.append(pid)
        return cancelled

    def grant_user_approval(self, request_id: str) -> None:
        """Record user approval and wake waiting processes."""
        from emergence.events.user_events import UserApprovalGrantedEvent

        self._ctx.state.set(f"approval:{request_id}", True)
        self._ctx.event_bus.publish(
            UserApprovalGrantedEvent(
                request_id=request_id,
                payload={"request_id": request_id},
            )
        )
        self._ctx.scheduler.evaluate_waiting()

    @property
    def context(self) -> KernelContext:
        """Return the kernel service container."""
        return self._ctx

    def _publish_shutdown(self) -> None:
        self._ctx.state.set("os:status", "stopped")
        self._ctx.event_bus.publish(
            Event(
                event_type=EventType.KERNEL_STOPPED,
                payload={"live_processes": self.live_process_count()},
            )
        )

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
            _state_store=self._ctx.state,
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
