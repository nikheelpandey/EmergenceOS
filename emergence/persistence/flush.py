from __future__ import annotations

from emergence.cognitive.manager import CognitiveManager
from emergence.kernel.context import KernelContext
from emergence.persistence.paths import (
    cognitive_path,
    goal_registry_path,
    knowledge_path,
    schedules_path,
    spaces_path,
    state_path,
)
from emergence.persistence.snapshots import (
    restore_cognitive_snapshot,
    restore_goal_registry_snapshot,
    restore_knowledge_snapshot,
    restore_schedules_snapshot,
    restore_spaces_snapshot,
    restore_state_snapshot,
    save_cognitive_snapshot,
    save_goal_registry_snapshot,
    save_knowledge_snapshot,
    save_schedules_snapshot,
    save_spaces_snapshot,
    save_state_snapshot,
)


def flush_persistence(ctx: KernelContext) -> None:
    """Persist runtime state and cognitive entities to disk."""
    save_state_snapshot(ctx.state, state_path())
    save_cognitive_snapshot(ctx.cognitive, cognitive_path())
    save_goal_registry_snapshot(ctx.goal_registry, goal_registry_path())
    save_knowledge_snapshot(ctx.knowledge_index, knowledge_path())
    save_spaces_snapshot(ctx.space_registry, spaces_path())
    save_schedules_snapshot(ctx.schedule_manager, schedules_path())
    ctx.checkpoints.close()


def restore_persistence(ctx: KernelContext) -> None:
    """Restore runtime state and cognitive entities from disk."""
    restore_state_snapshot(ctx.state, state_path())
    restore_cognitive_snapshot(ctx.cognitive, cognitive_path())
    restore_goal_registry_snapshot(ctx.goal_registry, goal_registry_path())
    restore_knowledge_snapshot(ctx.knowledge_index, knowledge_path())
    restore_spaces_snapshot(ctx.space_registry, spaces_path())
    restore_schedules_snapshot(ctx.schedule_manager, schedules_path())
