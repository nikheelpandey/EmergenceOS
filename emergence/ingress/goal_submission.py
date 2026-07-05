from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from emergence.cognitive.goal_registry import GoalKind

if TYPE_CHECKING:
    from emergence.core.ids import GoalID
    from emergence.kernel.kernel import Kernel


@dataclass(frozen=True, slots=True)
class GoalSubmissionResult:
    goal_id: str
    description: str
    mode: str
    process_id: str | None = None
    message: str = ""


def submit_goal(
    kernel: Kernel,
    description: str,
    *,
    mode: str = "goal",
    kind: GoalKind = GoalKind.ONE_SHOT,
    space_id: str | None = None,
    auto_approve: bool = False,
) -> GoalSubmissionResult:
    """Create a goal and optionally start work, shared by REPL and HTTP."""
    ctx = kernel.context
    active_space = space_id or ctx.space_registry.active_space_id

    if mode == "research":
        return _submit_research(kernel, description, space_id=active_space)

    goal = kernel.create_goal(description, kind=kind)
    ctx.goal_registry.set_space(goal.goal_id, active_space)

    if auto_approve:
        ctx.state.set("auto_approve", True)

    if mode == "plan":
        ctx.state.set("research_topic", description)
        kernel.start_planning(goal.goal_id)
        kernel.spawn_planner_for_goal(goal.goal_id)
        return GoalSubmissionResult(
            goal_id=str(goal.goal_id),
            description=description,
            mode=mode,
            message=f"Planner spawned for: {description}",
        )

    if mode == "worker":
        from emergence.cognitive.manager import TaskSpec

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
        return GoalSubmissionResult(
            goal_id=str(goal.goal_id),
            description=description,
            mode=mode,
            message=f"Goal created with worker plan: {description}",
        )

    return GoalSubmissionResult(
        goal_id=str(goal.goal_id),
        description=description,
        mode=mode,
        message=f"Goal created: {description}",
    )


def _submit_research(
    kernel: Kernel,
    topic: str,
    *,
    space_id: str,
) -> GoalSubmissionResult:
    ctx = kernel.context
    ctx.state.set("research_topic", topic)
    ctx.state.set("auto_approve", True)
    goal = kernel.create_goal(
        f"Research: {topic}",
        kind=GoalKind.PERSISTENT,
    )
    ctx.goal_registry.set_space(goal.goal_id, space_id)
    process = kernel.spawn(
        ctx.registry.get("research_assistant"),
        goal_id=goal.goal_id,
        priority=8,
    )
    return GoalSubmissionResult(
        goal_id=str(goal.goal_id),
        description=f"Research: {topic}",
        mode="research",
        process_id=str(process.process_id),
        message=f"Research assistant spawned for: {topic}",
    )
