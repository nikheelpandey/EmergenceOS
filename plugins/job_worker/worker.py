"""
Job worker — long-running process that handles jobs from its mailbox.

Each job is a Request(action=process_job). Results are stored in
working memory. Yields between jobs until shutdown.
"""

from __future__ import annotations

from emergence.apps.long_running_runtime import (
    drain_messages,
    get_stage,
    increment_stage,
    is_shutdown,
    respond,
)
from emergence.common.request import Request
from emergence.core.process_context import ProcessContext


def run(context: ProcessContext) -> str:
    jobs_done = get_stage(context)

    for message in drain_messages(context):
        if is_shutdown(message):
            context.state.set(f"worker:{context.process_id}:status", "stopped")
            return f"worker_stopped:{jobs_done}"

        if isinstance(message, Request) and message.action == "process_job":
            job_id = message.payload.get("job_id", "unknown")
            payload = message.payload.get("data", "")

            tool_result = context.tools.invoke(
                "echo",
                {"message": f"processed:{payload}"},
            )
            result = {
                "job_id": job_id,
                "output": tool_result.result,
                "worker": str(context.process_id),
            }

            context.memory.store(f"job:{job_id}", result)
            jobs_done = increment_stage(context)
            respond(context, message, result)

    context.state.set(
        f"worker:{context.process_id}:jobs_done",
        jobs_done,
    )

    context.wait_for_message()
    return "worker_waiting"
