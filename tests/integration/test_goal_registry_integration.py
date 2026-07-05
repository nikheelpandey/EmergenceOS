"""Integration tests for Goal Registry (M21)."""

from __future__ import annotations

import pytest

from emergence.admin.client import AdminClient
from emergence.cognitive.goal_registry import GoalHealth, GoalKind
from emergence.core.event import EventType
from emergence.core.process_context import ProcessContext
from emergence.core.process_definition import ProcessDefinition
from emergence.kernel.boot_context import build_research_assistant, create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.persistence.flush import flush_persistence
from emergence.persistence.paths import goal_registry_path
from tests.helpers_admin import short_data_dir


class FailingRunner:
    def run(self, context: ProcessContext) -> str:
        raise RuntimeError("child process failed")


@pytest.mark.integration
class TestGoalRegistryIntegration:
    def test_research_assistant_registered_as_persistent_goal(self):
        kernel, _ = build_research_assistant("quantum computing", auto_approve=True)
        views = kernel.context.goal_registry.list_views()
        assert views[0]["kind"] == "persistent"
        assert "quantum computing" in views[0]["description"]
        assert views[0]["stats"]["active_child_count"] >= 0
        assert views[0]["stats"]["uptime_seconds"] >= 0

    def test_health_degraded_when_child_process_fails(self):
        ctx = create_kernel_context()
        kernel = Kernel(
            ctx=ctx,
            executor=ctx.executor,
            lifecycle=LifecycleManager(),
        )
        goal = kernel.create_goal("Failing workload")
        definition = ProcessDefinition(
            name="failer",
            implementation="failer",
            version="1.0.0",
        )
        ctx.registry.register(definition)
        ctx.executor.register_runner("failer", FailingRunner())
        process = kernel.spawn(definition, goal_id=goal.goal_id)

        kernel.run_next()

        view = ctx.goal_registry.query(goal.goal_id)
        assert view is not None
        assert view["health"] == GoalHealth.DEGRADED.value
        assert str(process.process_id) in view["process_ids"]

    def test_goal_survives_kernel_restart(self, monkeypatch):
        data_dir = short_data_dir("goal-registry-persist")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        ctx1 = create_kernel_context(persist=True)
        kernel1 = Kernel(
            ctx=ctx1,
            executor=ctx1.executor,
            lifecycle=LifecycleManager(),
        )
        goal = kernel1.create_goal(
            "Persistent research",
            kind=GoalKind.PERSISTENT,
        )
        definition = ProcessDefinition(
            name="worker",
            implementation="worker",
            version="1.0.0",
        )
        ctx1.registry.register(definition)
        kernel1.spawn(definition, goal_id=goal.goal_id)
        flush_persistence(ctx1)
        ctx1.checkpoints.close()

        assert goal_registry_path().exists()

        ctx2 = create_kernel_context(persist=True)
        try:
            views = ctx2.goal_registry.list_views()
            assert len(views) == 1
            assert views[0]["goal_id"] == str(goal.goal_id)
            assert views[0]["kind"] == "persistent"
        finally:
            ctx2.checkpoints.close()

    def test_admin_goals_endpoint(self, monkeypatch):
        data_dir = short_data_dir("goal-registry-admin")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        from emergence.kernel.runtime import RuntimeService

        service = RuntimeService.start()
        try:
            goal = service.kernel.create_goal(
                "Admin visible goal",
                kind=GoalKind.PERSISTENT,
            )
            definition = service.kernel.context.registry.get("job_worker")
            service.kernel.spawn(definition, goal_id=goal.goal_id)

            client = AdminClient.connect()
            goals = client.call("goals")
            assert len(goals["goals"]) == 1

            detail = client.call(
                "goal.get",
                params={"goal_id": str(goal.goal_id)},
            )
            assert detail["goal_id"] == str(goal.goal_id)
            assert detail["health"] in {
                GoalHealth.HEALTHY.value,
                GoalHealth.IDLE.value,
            }
        finally:
            service.stop()

    def test_health_changed_event_emitted(self):
        ctx = create_kernel_context()
        kernel = Kernel(
            ctx=ctx,
            executor=ctx.executor,
            lifecycle=LifecycleManager(),
        )
        goal = kernel.create_goal("Event test")
        definition = ProcessDefinition(
            name="failer2",
            implementation="failer2",
            version="1.0.0",
        )
        ctx.registry.register(definition)
        ctx.executor.register_runner("failer2", FailingRunner())
        process = kernel.spawn(definition, goal_id=goal.goal_id)
        kernel.run_next()

        events = ctx.event_store.query(event_type=EventType.GOAL_HEALTH_CHANGED)
        assert any(
            event.payload.get("goal_id") == str(goal.goal_id)
            and event.payload.get("health") == GoalHealth.DEGRADED.value
            for event in events
        )
