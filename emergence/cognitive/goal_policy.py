from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from emergence.core.budget import ResourceBudget

SPEND_PRESETS: dict[str, ResourceBudget] = {
    "low": ResourceBudget(
        max_tokens=10_000,
        max_cost_usd=0.25,
        max_tool_invocations=30,
        max_execution_time_seconds=180,
    ),
    "medium": ResourceBudget(
        max_tokens=50_000,
        max_cost_usd=1.0,
        max_tool_invocations=100,
        max_execution_time_seconds=600,
    ),
    "high": ResourceBudget(
        max_tokens=200_000,
        max_cost_usd=5.0,
        max_tool_invocations=500,
        max_execution_time_seconds=3600,
    ),
}

WORKLOAD_MODES: dict[str, str] = {
    "research": "research_assistant",
    "goal": "goal",
    "worker": "worker",
    "plan": "planner",
}


@dataclass(slots=True)
class GoalPolicy:
    """User-facing guardrails and workload binding for a goal."""

    workload: str = "research"
    spend_preset: str = "medium"
    autonomy_preset: str = "ask"
    auto_approve: bool = False
    budget: ResourceBudget = field(default_factory=ResourceBudget)
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workload": self.workload,
            "spend_preset": self.spend_preset,
            "autonomy_preset": self.autonomy_preset,
            "auto_approve": self.auto_approve,
            "budget": {
                "max_tokens": self.budget.max_tokens,
                "max_cost_usd": self.budget.max_cost_usd,
                "max_tool_invocations": self.budget.max_tool_invocations,
                "max_execution_time_seconds": (
                    self.budget.max_execution_time_seconds
                ),
                "max_retries": self.budget.max_retries,
            },
            "config": dict(self.config),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> GoalPolicy:
        if not data:
            return resolve_goal_policy()
        spend = str(data.get("spend_preset", data.get("spend", "medium")))
        autonomy = str(
            data.get("autonomy_preset", data.get("autonomy", "ask"))
        )
        auto_approve = bool(data.get("auto_approve", False))
        if autonomy == "auto":
            auto_approve = True
        workload = str(data.get("workload", data.get("mode", "research")))
        budget_raw = data.get("budget")
        if isinstance(budget_raw, dict):
            budget = ResourceBudget(
                max_tokens=int(
                    budget_raw.get("max_tokens", SPEND_PRESETS["medium"].max_tokens)
                ),
                max_cost_usd=float(
                    budget_raw.get(
                        "max_cost_usd",
                        SPEND_PRESETS["medium"].max_cost_usd,
                    )
                ),
                max_tool_invocations=int(
                    budget_raw.get(
                        "max_tool_invocations",
                        SPEND_PRESETS["medium"].max_tool_invocations,
                    )
                ),
                max_execution_time_seconds=int(
                    budget_raw.get(
                        "max_execution_time_seconds",
                        SPEND_PRESETS["medium"].max_execution_time_seconds,
                    )
                ),
                max_retries=int(budget_raw.get("max_retries", 3)),
            )
        else:
            budget = SPEND_PRESETS.get(spend, SPEND_PRESETS["medium"])
        config = data.get("config")
        return cls(
            workload=workload,
            spend_preset=spend,
            autonomy_preset=autonomy,
            auto_approve=auto_approve,
            budget=budget,
            config=dict(config) if isinstance(config, dict) else {},
        )


def resolve_goal_policy(
    *,
    mode: str | None = None,
    workload: str | None = None,
    spend_preset: str | None = None,
    autonomy_preset: str | None = None,
    auto_approve: bool | None = None,
    policy: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> GoalPolicy:
    """Build a GoalPolicy from HTTP/CLI submission fields."""
    if policy:
        resolved = GoalPolicy.from_dict(policy)
    else:
        spend = spend_preset or "medium"
        autonomy = autonomy_preset
        if autonomy is None:
            if auto_approve is True:
                autonomy = "auto"
            elif auto_approve is False:
                autonomy = "ask"
            elif (workload or mode) == "research":
                autonomy = "auto"
            else:
                autonomy = "ask"
        resolved = GoalPolicy(
            workload=workload or mode or "research",
            spend_preset=spend,
            autonomy_preset=autonomy,
            auto_approve=autonomy == "auto",
            budget=SPEND_PRESETS.get(spend, SPEND_PRESETS["medium"]),
            config=dict(config) if config else {},
        )

    if auto_approve is not None:
        resolved.auto_approve = auto_approve
    if autonomy_preset == "auto":
        resolved.autonomy_preset = "auto"
        resolved.auto_approve = True
    if autonomy_preset == "ask":
        resolved.autonomy_preset = "ask"
        resolved.auto_approve = False

    if workload:
        resolved.workload = workload
    elif mode:
        resolved.workload = mode

    if spend_preset:
        resolved.spend_preset = spend_preset
        resolved.budget = SPEND_PRESETS.get(
            spend_preset,
            resolved.budget,
        )

    if config:
        resolved.config.update(config)

    return resolved


def apply_goal_runtime_config(
    ctx,
    goal_id,
    policy: GoalPolicy,
    *,
    description: str = "",
) -> None:
    """Write goal-scoped runtime configuration into the state store."""
    gid = str(goal_id)
    topic = policy.config.get("topic") or description
    ctx.state.set(f"goal:{gid}:auto_approve", policy.auto_approve)
    if topic:
        ctx.state.set(f"goal:{gid}:research_topic", topic)
