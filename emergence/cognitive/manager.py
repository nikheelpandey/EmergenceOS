from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from emergence.core.event import Event, EventType
from emergence.core.goal import Goal
from emergence.core.ids import GoalID, PlanID, ProcessID, TaskID
from emergence.core.plan import Plan
from emergence.core.state import GoalState, PlanState, TaskState
from emergence.core.task import Task
from emergence.events.event_bus import EventBus

if TYPE_CHECKING:
    from emergence.kernel.kernel import Kernel


class GoalNotFoundError(Exception):
    pass


class PlanNotFoundError(Exception):
    pass


class TaskNotFoundError(Exception):
    pass


@dataclass
class TaskSpec:
    """Blueprint for creating a task within a plan."""

    name: str
    process_definition_name: str
    dependencies: tuple[str, ...] = ()
    priority: int = 0
    expected_output: str = ""


@dataclass
class CognitiveManager:
    """
    Kernel-managed Goal → Plan → Task orchestration.

    The cognitive manager owns application-level entities and
    coordinates their lifecycle. It never invokes LLMs — plan
    decomposition is performed by planner processes or explicit
    task specifications.
    """

    event_bus: EventBus
    _goals: dict[str, Goal] = field(default_factory=dict)
    _plans: dict[str, Plan] = field(default_factory=dict)
    _tasks: dict[str, Task] = field(default_factory=dict)
    _tasks_by_plan: dict[str, list[str]] = field(default_factory=dict)
    _task_name_index: dict[str, dict[str, str]] = field(
        default_factory=dict
    )

    def create_goal(self, description: str) -> Goal:
        goal = Goal(description=description)
        self._goals[str(goal.goal_id)] = goal
        self._publish(
            EventType.GOAL_CREATED,
            payload={
                "goal_id": str(goal.goal_id),
                "description": description,
            },
        )
        return goal

    def start_planning(self, goal_id: GoalID) -> Goal:
        goal = self._get_goal(goal_id)
        goal.transition_to(GoalState.PLANNING)
        self._publish(
            EventType.GOAL_PLANNING,
            payload={"goal_id": str(goal_id)},
        )
        return goal

    def create_plan(
        self,
        goal_id: GoalID,
        task_specs: list[TaskSpec],
        *,
        priority: int = 0,
    ) -> Plan:
        goal = self._get_goal(goal_id)
        plan = Plan(goal_id=goal_id, priority=priority)
        plan_id = str(plan.plan_id)

        self._plans[plan_id] = plan
        self._tasks_by_plan[plan_id] = []
        self._task_name_index[plan_id] = {}

        name_to_id: dict[str, str] = {}

        for spec in task_specs:
            task = Task(
                plan_id=plan.plan_id,
                name=spec.name,
                process_definition_name=spec.process_definition_name,
                priority=spec.priority,
                expected_output=spec.expected_output,
            )
            tid = str(task.task_id)
            self._tasks[tid] = task
            self._tasks_by_plan[plan_id].append(tid)
            self._task_name_index[plan_id][spec.name] = tid
            name_to_id[spec.name] = tid

            self._publish(
                EventType.TASK_CREATED,
                payload={
                    "task_id": tid,
                    "plan_id": plan_id,
                    "name": spec.name,
                },
            )

        for spec in task_specs:
            tid = name_to_id[spec.name]
            task = self._tasks[tid]
            dep_ids = tuple(
                TaskID(name_to_id[dep_name])
                for dep_name in spec.dependencies
            )
            task.dependencies = dep_ids

        plan.transition_to(PlanState.ACTIVE)
        goal.transition_to(GoalState.IN_PROGRESS)

        self._publish(
            EventType.PLAN_CREATED,
            payload={"plan_id": plan_id, "goal_id": str(goal_id)},
        )
        self._publish(
            EventType.GOAL_IN_PROGRESS,
            payload={"goal_id": str(goal_id)},
        )

        self._update_ready_tasks(plan_id)
        return plan

    def execute_plan(self, kernel: Kernel, plan_id: PlanID) -> None:
        """Spawn processes for ready tasks and schedule with dependencies."""
        self._spawn_ready_tasks(kernel, plan_id)

    def on_process_completed(
        self,
        process_id: ProcessID,
        kernel: Kernel,
    ) -> None:
        """Mark the associated task complete and spawn newly ready tasks."""
        for task in self._tasks.values():
            if task.assigned_process_id != process_id:
                continue
            if task.is_finished:
                return

            task.transition_to(TaskState.COMPLETED)
            self._publish(
                EventType.TASK_COMPLETED,
                source_process=process_id,
                payload={
                    "task_id": str(task.task_id),
                    "plan_id": str(task.plan_id),
                },
            )

            plan_id = task.plan_id
            self._update_ready_tasks(str(plan_id))
            self._spawn_ready_tasks(kernel, plan_id)
            self._check_plan_completion(str(plan_id))
            return

    def on_process_failed(self, process_id: ProcessID) -> None:
        for task in self._tasks.values():
            if task.assigned_process_id != process_id:
                continue
            task.transition_to(TaskState.FAILED)
            self._publish(
                EventType.TASK_FAILED,
                source_process=process_id,
                payload={"task_id": str(task.task_id)},
            )
            plan = self._plans[str(task.plan_id)]
            plan.transition_to(PlanState.FAILED)
            goal = self._goals[str(plan.goal_id)]
            goal.transition_to(GoalState.FAILED)
            self._publish(
                EventType.GOAL_FAILED,
                payload={"goal_id": str(plan.goal_id)},
            )
            return

    def ready_tasks(self, plan_id: PlanID) -> list[Task]:
        return [
            self._tasks[tid]
            for tid in self._tasks_by_plan.get(str(plan_id), [])
            if self._tasks[tid].state == TaskState.READY
        ]

    def _spawn_ready_tasks(self, kernel: Kernel, plan_id: PlanID) -> None:
        plan = self._get_plan(plan_id)
        if plan.state != PlanState.ACTIVE:
            return

        for task in self.ready_tasks(plan_id):
            if task.assigned_process_id is not None:
                continue

            definition = kernel.context.registry.get(
                task.process_definition_name
            )

            process = kernel.spawn(
                definition,
                goal_id=plan.goal_id,
                priority=task.priority,
            )
            task.assigned_process_id = process.process_id
            task.transition_to(TaskState.RUNNING)
            self._publish(
                EventType.TASK_STARTED,
                source_process=process.process_id,
                payload={
                    "task_id": str(task.task_id),
                    "plan_id": str(plan_id),
                },
            )

    def tasks_for_plan(self, plan_id: PlanID) -> list[Task]:
        return [
            self._tasks[tid]
            for tid in self._tasks_by_plan.get(str(plan_id), [])
        ]

    def get_goal(self, goal_id: GoalID) -> Goal:
        return self._get_goal(goal_id)

    def get_plan(self, plan_id: PlanID) -> Plan:
        return self._get_plan(plan_id)

    def get_task(self, task_id: TaskID) -> Task:
        return self._get_task(task_id)

    def _update_ready_tasks(self, plan_id: str) -> None:
        for tid in self._tasks_by_plan.get(plan_id, []):
            task = self._tasks[tid]
            if task.state != TaskState.PENDING:
                continue
            if self._dependencies_met(task):
                task.transition_to(TaskState.READY)
                self._publish(
                    EventType.TASK_READY,
                    payload={
                        "task_id": tid,
                        "plan_id": plan_id,
                    },
                )

    def _dependencies_met(self, task: Task) -> bool:
        for dep_id in task.dependencies:
            dep = self._tasks[str(dep_id)]
            if dep.state != TaskState.COMPLETED:
                return False
        return True

    def _check_plan_completion(self, plan_id: str) -> None:
        tasks = [
            self._tasks[tid]
            for tid in self._tasks_by_plan.get(plan_id, [])
        ]
        if tasks and all(t.state == TaskState.COMPLETED for t in tasks):
            plan = self._plans[plan_id]
            plan.transition_to(PlanState.COMPLETED)
            self._publish(
                EventType.PLAN_COMPLETED,
                payload={"plan_id": plan_id},
            )
            goal = self._goals[str(plan.goal_id)]
            goal.transition_to(GoalState.COMPLETED)
            self._publish(
                EventType.GOAL_COMPLETED,
                payload={"goal_id": str(plan.goal_id)},
            )

    def _get_goal(self, goal_id: GoalID) -> Goal:
        goal = self._goals.get(str(goal_id))
        if goal is None:
            raise GoalNotFoundError(f"Goal '{goal_id}' not found.")
        return goal

    def _get_plan(self, plan_id: PlanID) -> Plan:
        plan = self._plans.get(str(plan_id))
        if plan is None:
            raise PlanNotFoundError(f"Plan '{plan_id}' not found.")
        return plan

    def _get_task(self, task_id: TaskID) -> Task:
        task = self._tasks.get(str(task_id))
        if task is None:
            raise TaskNotFoundError(f"Task '{task_id}' not found.")
        return task

    def _publish(
        self,
        event_type: EventType,
        *,
        source_process: ProcessID | None = None,
        payload: dict | None = None,
        correlation_id: UUID | None = None,
    ) -> None:
        self.event_bus.publish(
            Event(
                event_type=event_type,
                source_process=source_process,
                correlation_id=correlation_id,
                payload=payload or {},
            )
        )
