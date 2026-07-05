"""Integration tests for Spaces (M27)."""

from __future__ import annotations

import pytest

from emergence.core.process_definition import ProcessDefinition
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.memory.memory_category import MemoryCategory


@pytest.mark.integration
class TestSpacesIntegration:
    def test_isolated_knowledge_by_space(self):
        ctx = create_kernel_context()
        kernel = Kernel(ctx=ctx, executor=ctx.executor, lifecycle=LifecycleManager())

        work = ctx.space_registry.create("Work")
        personal = ctx.space_registry.create("Personal")

        work_goal = kernel.create_goal("Work goal")
        ctx.goal_registry.set_space(work_goal.goal_id, work.space_id)

        personal_goal = kernel.create_goal("Personal goal")
        ctx.goal_registry.set_space(personal_goal.goal_id, personal.space_id)

        definition = ProcessDefinition(
            name="worker",
            implementation="worker",
            version="1.0.0",
        )
        ctx.registry.register(definition)
        work_process = kernel.spawn(definition, goal_id=work_goal.goal_id)
        personal_process = kernel.spawn(definition, goal_id=personal_goal.goal_id)

        ctx.memory.store(
            work_process.process_id,
            "findings",
            "work finding",
            category=MemoryCategory.EPISODIC,
        )
        ctx.memory.store(
            personal_process.process_id,
            "findings",
            "personal finding",
            category=MemoryCategory.EPISODIC,
        )

        work_artifacts = ctx.knowledge_index.query(space_id=work.space_id)
        personal_artifacts = ctx.knowledge_index.query(space_id=personal.space_id)

        assert len(work_artifacts) == 1
        assert len(personal_artifacts) == 1
        assert work_artifacts[0]["space_id"] == work.space_id
        assert personal_artifacts[0]["space_id"] == personal.space_id
