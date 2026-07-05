"""
Planner plugin — deterministic goal decomposition.

Reads task specifications from state and writes a plan request.
The kernel CognitiveManager performs actual plan creation; this
process never calls an LLM.
"""

from __future__ import annotations

import json

from emergence.core.process_context import ProcessContext


def run(context: ProcessContext) -> str:
    raw = context.state.get("task_specs")
    if raw is None:
        raise RuntimeError("task_specs not set in state for planner")

    specs = json.loads(raw) if isinstance(raw, str) else raw
    context.state.set("plan_request", json.dumps(specs))
    return "planning_complete"
