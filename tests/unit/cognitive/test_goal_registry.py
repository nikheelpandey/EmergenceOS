"""Unit tests for GoalRegistry (M21)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from emergence.cognitive.goal_registry import (
    GoalHealth,
    GoalKind,
    GoalRegistry,
)
from emergence.core.budget import ResourceBudget
from emergence.core.event import Event, EventType
from emergence.core.ids import GoalID, ProcessID
from emergence.core.process import Process
from emergence.core.process_definition import ProcessDefinition
from emergence.events.event_bus import EventBus
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager


@pytest.mark.unit
class TestGoalRegistry:
    def test_register_and_query_goal(self):
        bus = EventBus()
        registry = GoalRegistry(bus, staleness_seconds=3600.0)
        goal_id = GoalID.new()

        registry.register(goal_id, "Research topic", kind=GoalKind.PERSISTENT)
        view = registry.query(goal_id)

        assert view is not None
        assert view["description"] == "Research topic"
        assert view["kind"] == "persistent"
        assert view["health"] == "healthy"

    def test_associates_process_with_goal(self):
        bus = EventBus()
        registry = GoalRegistry(bus)
        goal_id = GoalID.new()
        process_id = ProcessID.new()

        registry.register(goal_id, "Workload")
        registry.associate_process(goal_id, process_id, as_root=True)

        assert registry.goal_for_process(process_id) == goal_id
        view = registry.query(goal_id)
        assert view is not None
        assert str(process_id) in view["process_ids"]

    def test_health_degraded_on_process_failure_event(self):
        bus = EventBus()
        registry = GoalRegistry(bus)
        goal_id = GoalID.new()
        process_id = ProcessID.new()

        registry.register(goal_id, "Workload")
        registry.associate_process(goal_id, process_id)

        bus.publish(
            Event(
                event_type=EventType.PROCESS_FAILED,
                source_process=process_id,
                payload={"error": "runner crashed"},
            )
        )

        view = registry.query(goal_id)
        assert view is not None
        assert view["health"] == "degraded"

    def test_health_degraded_on_budget_failure(self):
        bus = EventBus()
        registry = GoalRegistry(bus)
        goal_id = GoalID.new()
        process_id = ProcessID.new()

        registry.register(goal_id, "Workload")
        registry.associate_process(goal_id, process_id)

        bus.publish(
            Event(
                event_type=EventType.PROCESS_FAILED,
                source_process=process_id,
                payload={"error": "Resource budget exhausted before dispatch."},
            )
        )

        record = registry.get(goal_id)
        assert record is not None
        assert record.has_budget_exceeded is True

    def test_one_shot_goal_archived_on_completion(self):
        bus = EventBus()
        registry = GoalRegistry(bus)
        goal_id = GoalID.new()
        registry.register(goal_id, "One shot", kind=GoalKind.ONE_SHOT)

        bus.publish(
            Event(
                event_type=EventType.GOAL_COMPLETED,
                payload={"goal_id": str(goal_id)},
            )
        )

        record = registry.get(goal_id)
        assert record is not None
        assert record.archived is True
        assert registry.list_all() == []

    def test_snapshot_round_trip(self):
        bus = EventBus()
        registry = GoalRegistry(bus)
        goal_id = GoalID.new()
        process_id = ProcessID.new()
        registry.register(goal_id, "Persist me", kind=GoalKind.PERSISTENT)
        registry.associate_process(goal_id, process_id)

        data = registry.snapshot()
        restored = GoalRegistry(EventBus())
        restored.restore(data)

        view = restored.query(goal_id)
        assert view is not None
        assert view["description"] == "Persist me"
        assert str(process_id) in view["process_ids"]

    def test_kernel_spawn_associates_goal(self):
        ctx = create_kernel_context()
        kernel = Kernel(
            ctx=ctx,
            executor=ctx.executor,
            lifecycle=LifecycleManager(),
        )
        goal = kernel.create_goal("Demo goal")
        definition = ProcessDefinition(
            name="worker",
            implementation="worker",
            version="1.0.0",
        )
        ctx.registry.register(definition)
        process = kernel.spawn(definition, goal_id=goal.goal_id)

        view = ctx.goal_registry.query(goal.goal_id)
        assert view is not None
        assert str(process.process_id) in view["process_ids"]

    def test_live_health_from_process_table(self):
        ctx = create_kernel_context()
        registry = ctx.goal_registry
        goal_id = GoalID.new()
        process_id = ProcessID.new()
        registry.register(goal_id, "Live health")

        definition = ProcessDefinition(
            name="flaky",
            implementation="flaky",
            version="1.0.0",
        )
        process = Process(
            definition=definition,
            goal_id=goal_id,
            process_id=process_id,
        )
        lifecycle = LifecycleManager()
        lifecycle.ready(process)
        lifecycle.start(process)
        lifecycle.fail(process, "boom")
        ctx.process_table.add(process)
        registry.associate_process(goal_id, process_id)

        record = registry.get(goal_id)
        assert record is not None
        assert registry.compute_health(record) == GoalHealth.DEGRADED

    def test_needs_attention_for_stale_approval(self, monkeypatch):
        ctx = create_kernel_context()
        registry = GoalRegistry(
            ctx.event_bus,
            approval_threshold_seconds=1.0,
        )
        registry.bind_context(ctx)
        goal_id = GoalID.new()
        process_id = ProcessID.new()
        registry.register(goal_id, "Approval goal")
        registry.associate_process(goal_id, process_id)

        monkeypatch.setattr(
            "emergence.cognitive.goal_registry._pending_approvals_for_goal",
            lambda record, ctx: [
                {
                    "request_id": "req-old",
                    "timestamp": datetime.now(UTC) - timedelta(seconds=120),
                }
            ],
        )

        record = registry.get(goal_id)
        assert record is not None
        assert registry.compute_health(record) == GoalHealth.NEEDS_ATTENTION

    def test_idle_when_stale(self):
        bus = EventBus()
        registry = GoalRegistry(bus, staleness_seconds=10.0)
        goal_id = GoalID.new()
        record = registry.register(goal_id, "Idle goal")
        record.last_event_at = datetime.now(UTC) - timedelta(seconds=60)

        assert registry.compute_health(record) == GoalHealth.IDLE

    def test_stats_include_active_children_and_knowledge(self):
        ctx = create_kernel_context()
        registry = ctx.goal_registry
        goal_id = GoalID.new()
        process_id = ProcessID.new()
        registry.register(goal_id, "Stats goal")
        registry.associate_process(goal_id, process_id)

        definition = ProcessDefinition(
            name="worker",
            implementation="worker",
            version="1.0.0",
            default_budget=ResourceBudget(max_execution_time_seconds=60),
        )
        process = Process(definition=definition, process_id=process_id)
        lifecycle = LifecycleManager()
        lifecycle.ready(process)
        lifecycle.start(process)
        ctx.process_table.add(process)
        from emergence.memory.memory_category import MemoryCategory

        ctx.memory.store(
            process_id,
            "finding",
            "hello world",
            category=MemoryCategory.EPISODIC,
        )

        record = registry.get(goal_id)
        assert record is not None
        stats = registry.compute_stats(record)
        assert stats.active_child_count == 1
        assert stats.knowledge_size_bytes > 0
