"""
emergence/apps/system_model_demo.py

Simulates the EmergenceOS system model:

    Coordinator → Researcher → Evaluator

Demonstrates M3 (capability-gated IPC, request/response) and M4
(event-driven scheduling, WAITING, priorities, dependencies, budgets).
"""

from __future__ import annotations

from emergence.common.request import Request
from emergence.common.response import Response
from emergence.core.process_context import ProcessContext


def run_coordinator(context: ProcessContext) -> str:
    """
    Orchestrates the research pipeline.

    Sends a research request to the researcher process and waits
    for the correlated response.
    """
    researcher_pid = context.state.get("researcher_pid")
    if researcher_pid is None:
        raise RuntimeError("researcher_pid not configured in state")

    if context.mailboxes.pending() > 0:
        message = context.mailboxes.receive()
        if isinstance(message, Response) and message.success:
            context.state.set(
                "pipeline_status",
                f"coordinator_received:{message.result}",
            )
            return "coordinator_done"

    request = Request(
        sender_pid=str(context.process_id),
        recipient_pid=researcher_pid,
        action="research",
        payload={"topic": "emergence os architecture"},
    )
    context.mailboxes.send(request)
    context.state.set("pipeline_status", "request_sent")
    context.wait_for_message()

    return "coordinator_waiting"


def run_researcher(context: ProcessContext) -> str:
    """
    Receives research requests, produces findings, and responds.
    """
    if context.mailboxes.pending() == 0:
        context.wait_for_message()

    message = context.mailboxes.receive()
    if not isinstance(message, Request):
        raise RuntimeError(f"Expected Request, got {type(message)}")

    findings = (
        f"Research complete on '{message.payload['topic']}': "
        "event-driven processes with capability-based security."
    )
    context.state.set("research_findings", findings)

    response = Response(
        sender_pid=str(context.process_id),
        recipient_pid=message.sender_pid,
        payload={"findings": findings},
        correlation_id=message.correlation_id,
        result=findings,
    )
    context.mailboxes.send(response)

    context.state.set("pipeline_status", "research_complete")
    return "researcher_done"


def run_evaluator(context: ProcessContext) -> str:
    """
    Evaluates research findings after the researcher completes.
    """
    findings = context.state.get("research_findings")
    if findings is None:
        raise RuntimeError("No research findings available")

    score = min(len(findings) // 10, 10)
    evaluation = f"score={score}/10: {findings[:60]}..."

    context.state.set("evaluation", evaluation)
    context.state.set("pipeline_status", "goal_completed")
    return evaluation


def run_restricted(context: ProcessContext) -> str:
    """
    A process with read-only state access — write should fail.
    """
    context.state.get("research_findings", "none")
    context.state.set("should_fail", True)
    return "should_not_reach"
