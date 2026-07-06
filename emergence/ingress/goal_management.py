from __future__ import annotations

from typing import TYPE_CHECKING, Any

from emergence.cognitive.goal_policy import (
    GoalPolicy,
    apply_goal_runtime_config,
    resolve_goal_policy,
)
from emergence.cognitive.goal_registry import GoalKind, GoalNotRegisteredError
from emergence.core.event import Event, EventType
from emergence.core.ids import GoalID, ProcessID
from emergence.core.state import ProcessState

if TYPE_CHECKING:
    from emergence.kernel.kernel import Kernel


class GoalManagementError(Exception):
    pass


def update_goal(
    kernel: Kernel,
    goal_id: str,
    *,
    description: str | None = None,
    spend_preset: str | None = None,
    autonomy_preset: str | None = None,
    auto_approve: bool | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update goal metadata and/or policy."""
    ctx = kernel.context
    parsed = GoalID.from_string(goal_id)
    record = ctx.goal_registry.get(parsed)
    if record is None:
        raise GoalNotRegisteredError(goal_id)

    if description is not None:
        record.description = description.strip()
        if not record.description:
            raise GoalManagementError("description cannot be empty")

    if any(
        value is not None
        for value in (spend_preset, autonomy_preset, auto_approve, policy)
    ):
        base = record.policy.to_dict() if record.policy else {"workload": record.workload}
        if policy:
            base.update(policy)
        if spend_preset:
            base["spend_preset"] = spend_preset
        if autonomy_preset:
            base["autonomy_preset"] = autonomy_preset
        if auto_approve is not None:
            base["auto_approve"] = auto_approve
        base.setdefault("workload", record.workload)
        resolved = resolve_goal_policy(policy=base)
        ctx.goal_registry.set_policy(parsed, resolved)
        apply_goal_runtime_config(
            ctx,
            parsed,
            resolved,
            description=record.description,
        )

    view = ctx.goal_registry.query(parsed)
    if view is None:
        raise GoalNotRegisteredError(goal_id)
    return view


def cancel_goal(kernel: Kernel, goal_id: str) -> dict[str, Any]:
    """Cancel all active processes for a goal."""
    parsed = GoalID.from_string(goal_id)
    cancelled = kernel.cancel_goal_processes(parsed)
    record = kernel.context.goal_registry.get(parsed)
    if record is not None:
        record.pipeline_stage = "cancelled"
        kernel.context.event_bus.publish(
            Event(
                event_type=EventType.GOAL_CANCELLED,
                payload={"goal_id": goal_id, "cancelled_processes": cancelled},
            )
        )
    return {
        "goal_id": goal_id,
        "cancelled_processes": cancelled,
        "status": "cancelled",
    }


def archive_goal(kernel: Kernel, goal_id: str) -> dict[str, Any]:
    """Cancel processes and archive a goal (soft delete)."""
    ctx = kernel.context
    parsed = GoalID.from_string(goal_id)
    record = ctx.goal_registry.get(parsed)
    if record is None:
        raise GoalNotRegisteredError(goal_id)

    cancel_goal(kernel, goal_id)
    record.archived = True
    record.pipeline_stage = "archived"
    return {"goal_id": goal_id, "archived": True}


def delete_goal(kernel: Kernel, goal_id: str, *, hard: bool = False) -> dict[str, Any]:
    """Archive a goal, or remove it from the registry when hard=True."""
    ctx = kernel.context
    parsed = GoalID.from_string(goal_id)
    if ctx.goal_registry.get(parsed) is None:
        raise GoalNotRegisteredError(goal_id)

    cancel_goal(kernel, goal_id)
    if hard:
        ctx.goal_registry.remove(parsed)
        return {"goal_id": goal_id, "deleted": True}
    return archive_goal(kernel, goal_id)


def rerun_goal(kernel: Kernel, goal_id: str) -> dict[str, Any]:
    """Cancel current work and restart the goal's workload."""
    from emergence.ingress.goal_submission import start_goal_work

    ctx = kernel.context
    parsed = GoalID.from_string(goal_id)
    record = ctx.goal_registry.get(parsed)
    if record is None:
        raise GoalNotRegisteredError(goal_id)
    if record.policy is None:
        raise GoalManagementError("goal has no policy — cannot rerun")

    cancel_goal(kernel, goal_id)
    ctx.goal_registry.reset_for_rerun(parsed)

    description = _workload_description(record.description, record.policy)
    process_id = start_goal_work(
        kernel,
        parsed,
        description,
        record.policy,
        space_id=record.space_id,
    )
    view = ctx.goal_registry.query(parsed)
    return {
        "goal_id": goal_id,
        "status": "rerunning",
        "process_id": process_id,
        "goal": view,
    }


def _workload_description(description: str, policy: GoalPolicy) -> str:
    if policy.workload == "research":
        if description.lower().startswith("research:"):
            return description.split(":", 1)[-1].strip()
        return policy.config.get("topic") or description
    return description
