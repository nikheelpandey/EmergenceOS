"""
Planner plugin — LLM-driven goal decomposition.

Invokes ``llm.chat`` to produce a TaskSpec JSON artifact stored
in state as ``plan_artifact``. The kernel never calls an LLM.
"""

from __future__ import annotations

from emergence.core.process_context import ProcessContext
from emergence.tools.json_utils import extract_json


def run(context: ProcessContext) -> str:
    goal = context.state.get("planning_goal")
    if goal is None:
        raise RuntimeError("planning_goal not set in state for planner")

    prompt = (
        f"Decompose this goal into a JSON array of tasks:\n\n"
        f"Goal: {goal}\n\n"
        f"Return ONLY a JSON array where each element has:\n"
        f'name, process_definition_name ("researcher" or "evaluator"), '
        f"dependencies (array of task names), priority (int), "
        f"expected_output (string).\n"
        f"Include at least: research, evaluate (depends on research), "
        f"and report (depends on evaluate) tasks."
    )

    result = context.tools.invoke(
        "llm.chat",
        {
            "prompt": prompt,
            "system": (
                "You are a task planner. Output valid JSON arrays only."
            ),
        },
    )

    if not result.success:
        raise RuntimeError(f"LLM planning failed: {result.error}")

    content = result.result
    specs = extract_json(content) if isinstance(content, str) else content

    import json
    context.state.set("plan_artifact", json.dumps(specs))
    return "planning_complete"
