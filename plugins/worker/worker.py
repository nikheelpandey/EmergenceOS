"""Generic worker plugin for cognitive task execution."""

from __future__ import annotations

from emergence.core.process_context import ProcessContext


def run(context: ProcessContext) -> str:
    key = f"task_result:{context.process_id}"
    context.state.set(key, f"completed:{context.definition.name}")
    return f"worker:{context.definition.name}:done"
