"""Format research assistant output for CLI display."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from emergence.kernel.kernel import Kernel


def _llm_provider_label() -> str | None:
    provider = os.environ.get("EMERGENCE_LLM_PROVIDER", "mock").lower()
    if provider == "mock":
        return (
            "LLM: mock (offline demo). Set EMERGENCE_LLM_PROVIDER=ollama "
            "or openai for real research."
        )
    return f"LLM: {provider}"


def format_research_output(kernel: Kernel) -> str:
    """Return a human-readable summary of the research pipeline result."""
    ctx = kernel.context
    topic = ctx.state.get("research_topic")
    status = ctx.state.get("pipeline_status", "unknown")
    evaluation = ctx.state.get("evaluation")
    report = ctx.state.get("research_report")
    findings = ctx.state.get("research_findings")

    lines = []
    if topic:
        lines.append(f"Topic: {topic}")
    lines.append(f"Pipeline status: {status}")
    provider_note = _llm_provider_label()
    if provider_note:
        lines.append(provider_note)
    if evaluation:
        lines.append(f"Evaluation: {evaluation}")

    goals = ctx.goal_registry.list_views()
    if goals:
        goal = goals[-1]
        lines.append(
            f"Goal: {goal['description']} "
            f"({goal['health']}, {goal['stats']['active_child_count']} active)"
        )

    if report:
        lines.extend(["", "——— Research Report ———", "", str(report)])
    elif findings:
        lines.extend(["", "——— Findings ———", "", str(findings)])
    else:
        lines.append("")
        lines.append("No report generated yet.")

    return "\n".join(lines)
