from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from emergence.cognitive.goal_policy import (
    GoalPolicy,
    apply_goal_runtime_config,
    resolve_goal_policy,
)
from emergence.cognitive.goal_registry import GoalKind
from emergence.core.ids import GoalID

if TYPE_CHECKING:
    from emergence.kernel.kernel import Kernel


@dataclass(frozen=True, slots=True)
class GoalSubmissionResult:
    goal_id: str
    description: str
    mode: str
    process_id: str | None = None
    message: str = ""
    policy: dict[str, Any] | None = None


def submit_goal(
    kernel: Kernel,
    description: str,
    *,
    mode: str = "goal",
    workload: str | None = None,
    kind: GoalKind = GoalKind.ONE_SHOT,
    space_id: str | None = None,
    auto_approve: bool | None = None,
    spend_preset: str | None = None,
    autonomy_preset: str | None = None,
    policy: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> GoalSubmissionResult:
    """Create a goal and optionally start work, shared by REPL and HTTP."""
    ctx = kernel.context
    active_space = space_id or ctx.space_registry.active_space_id
    resolved_policy = resolve_goal_policy(
        mode=mode,
        workload=workload,
        spend_preset=spend_preset,
        autonomy_preset=autonomy_preset,
        auto_approve=auto_approve,
        policy=policy,
        config=config,
    )
    effective_mode = resolved_policy.workload

    if effective_mode == "research":
        return _submit_research(
            kernel,
            description,
            space_id=active_space,
            goal_policy=resolved_policy,
        )

    goal = kernel.create_goal(description, kind=kind)
    ctx.goal_registry.set_space(goal.goal_id, active_space)
    ctx.goal_registry.set_policy(goal.goal_id, resolved_policy)

    process_id = start_goal_work(
        kernel,
        goal.goal_id,
        description,
        resolved_policy,
        space_id=active_space,
    )
    return _result(
        goal.goal_id,
        description,
        effective_mode,
        _message_for_mode(effective_mode, description),
        resolved_policy,
        process_id=process_id,
    )


def start_goal_work(
    kernel: Kernel,
    goal_id: GoalID,
    description: str,
    goal_policy: GoalPolicy,
    *,
    space_id: str | None = None,
) -> str | None:
    """Start or restart workload processes for an existing goal."""
    ctx = kernel.context
    apply_goal_runtime_config(
        ctx,
        goal_id,
        goal_policy,
        description=description,
    )

    if goal_policy.auto_approve:
        ctx.state.set("auto_approve", True)

    mode = goal_policy.workload
    if mode == "research":
        return _spawn_research(kernel, goal_id, goal_policy)

    if mode == "plan":
        ctx.state.set("research_topic", description)
        kernel.start_planning(goal_id)
        process = kernel.spawn_planner_for_goal(goal_id)
        return str(process.process_id)

    if mode == "worker":
        from emergence.cognitive.manager import TaskSpec

        kernel.start_planning(goal_id)
        plan = kernel.create_plan(
            goal_id,
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
        return None

    return None


def _message_for_mode(mode: str, description: str) -> str:
    if mode == "plan":
        return f"Planner spawned for: {description}"
    if mode == "worker":
        return f"Goal created with worker plan: {description}"
    return f"Goal created: {description}"


def _result(
    goal_id,
    description: str,
    mode: str,
    message: str,
    goal_policy: GoalPolicy,
    *,
    process_id: str | None = None,
) -> GoalSubmissionResult:
    return GoalSubmissionResult(
        goal_id=str(goal_id),
        description=description,
        mode=mode,
        process_id=process_id,
        message=message,
        policy=goal_policy.to_dict(),
    )


def _submit_research(
    kernel: Kernel,
    topic: str,
    *,
    space_id: str,
    goal_policy: GoalPolicy,
) -> GoalSubmissionResult:
    ctx = kernel.context
    goal = kernel.create_goal(
        f"Research: {topic}",
        kind=GoalKind.PERSISTENT,
    )
    ctx.goal_registry.set_space(goal.goal_id, space_id)
    ctx.goal_registry.set_policy(goal.goal_id, goal_policy)

    process_id = start_goal_work(
        kernel,
        goal.goal_id,
        topic,
        goal_policy,
        space_id=space_id,
    )
    return _result(
        goal.goal_id,
        f"Research: {topic}",
        "research",
        f"Research assistant spawned for: {topic}",
        goal_policy,
        process_id=process_id,
    )


def _spawn_research(
    kernel: Kernel,
    goal_id: GoalID,
    goal_policy: GoalPolicy,
) -> str:
    ctx = kernel.context
    process = kernel.spawn(
        ctx.registry.get("research_assistant"),
        goal_id=goal_id,
        priority=8,
        budget=goal_policy.budget,
    )
    return str(process.process_id)
