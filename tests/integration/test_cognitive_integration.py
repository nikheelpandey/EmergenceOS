"""Tests for emergence.cognitive — M12."""

from __future__ import annotations

from emergence.core.event import EventType
from emergence.core.process_context import ProcessContext
from emergence.core.state import GoalState, PlanState, TaskState
from emergence.cognitive.manager import CognitiveManager, TaskSpec
from emergence.events.event_bus import EventBus
from emergence.executor.executor import Executor
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager


class TestCognitiveManager:
    def test_goal_lifecycle_transitions(self):
        mgr = CognitiveManager(event_bus=EventBus())
        goal = mgr.create_goal("Write technical report")
        assert goal.state == GoalState.CREATED

        mgr.start_planning(goal.goal_id)
        assert goal.state == GoalState.PLANNING

    def test_create_plan_with_dependencies(self):
        mgr = CognitiveManager(event_bus=EventBus())
        goal = mgr.create_goal("Analyze data")
        mgr.start_planning(goal.goal_id)

        plan = mgr.create_plan(
            goal.goal_id,
            [
                TaskSpec("research", "worker", priority=5),
                TaskSpec(
                    "summarize",
                    "worker",
                    dependencies=("research",),
                    priority=3,
                ),
            ],
        )

        assert plan.state == PlanState.ACTIVE
        assert goal.state == GoalState.IN_PROGRESS
        ready = mgr.ready_tasks(plan.plan_id)
        assert len(ready) == 1
        assert ready[0].name == "research"


class TestCognitiveIntegration:
    def test_goal_plan_tasks_execute_end_to_end(self):
        executor = Executor()
        ctx = create_kernel_context(executor=executor)
        ctx.plugins.load(PLUGINS_ROOT / "worker")

        kernel = Kernel(
            ctx=ctx,
            executor=ctx.executor,
            lifecycle=LifecycleManager(),
        )

        goal = kernel.create_goal("Write technical report")
        kernel.start_planning(goal.goal_id)

        plan = kernel.create_plan(
            goal.goal_id,
            [
                TaskSpec("research", "worker", priority=5),
                TaskSpec(
                    "summarize",
                    "worker",
                    dependencies=("research",),
                    priority=3,
                ),
            ],
        )

        kernel.execute_plan(plan.plan_id)
        kernel.run()

        assert goal.state == GoalState.COMPLETED
        assert plan.state == PlanState.COMPLETED

        tasks = ctx.cognitive.tasks_for_plan(plan.plan_id)
        assert all(t.state == TaskState.COMPLETED for t in tasks)


from pathlib import Path

PLUGINS_ROOT = Path(__file__).resolve().parents[2] / "plugins"
