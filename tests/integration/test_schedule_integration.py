"""Integration tests for scheduled work (M28)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from emergence.core.process_definition import ProcessDefinition
from emergence.events.narrative import build_timeline
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager


@pytest.mark.integration
class TestScheduleIntegration:
    def test_scheduled_entry_appears_on_timeline(self):
        ctx = create_kernel_context()
        kernel = Kernel(ctx=ctx, executor=ctx.executor, lifecycle=LifecycleManager())
        goal = kernel.create_goal("Scheduled publication")

        fire_at = datetime.now(UTC) + timedelta(hours=2)
        ctx.schedule_manager.register(
            goal.goal_id,
            "worker",
            fire_at,
            description="Tomorrow: scheduled publication",
        )

        timeline = build_timeline(ctx, goal_id=goal.goal_id)
        scheduled = timeline["scheduled"]
        assert len(scheduled) == 1
        assert "scheduled publication" in scheduled[0]["narrative"].lower()

    def test_due_schedule_spawns_process(self):
        ctx = create_kernel_context()
        kernel = Kernel(ctx=ctx, executor=ctx.executor, lifecycle=LifecycleManager())
        definition = ProcessDefinition(
            name="worker",
            implementation="worker",
            version="1.0.0",
        )
        ctx.registry.register(definition)
        goal = kernel.create_goal("Due schedule")

        fire_at = datetime.now(UTC) - timedelta(seconds=1)
        ctx.schedule_manager.register(
            goal.goal_id,
            "worker",
            fire_at,
            description="Due now",
        )

        before = kernel.process_count()
        spawned = ctx.schedule_manager.process_due(kernel)
        after = kernel.process_count()

        assert spawned
        assert after >= before
