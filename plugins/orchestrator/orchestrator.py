"""
Orchestrator — drives long-running services through a multi-phase scenario.

Phases (persisted in working memory):
  0. Ping heartbeat, wait for response
  1. Emit events to collector
  2. Dispatch jobs to workers
  3. Shutdown all services and complete
"""

from __future__ import annotations

from emergence.apps.long_running_runtime import (
    drain_messages,
    get_stage,
    set_stage,
)
from emergence.common.notification import Notification
from emergence.common.request import Request
from emergence.core.process_context import ProcessContext


def run(context: ProcessContext) -> str:
    messages = drain_messages(context)
    stage = get_stage(context)
    services = _service_pids(context)

    # Stage 0 → 1: wait for ping response before advancing
    if stage == 0:
        if not _got_ping_response(messages):
            _send_ping(context, services["heartbeat"])
            context.wait_for_message()
        set_stage(context, 1)
        stage = 1

    # Stage 1 → 2: emit events (no response needed)
    if stage == 1:
        _emit_events(context, services["collector"])
        set_stage(context, 2)
        stage = 2

    # Stage 2 → 3: dispatch jobs (workers reply but we don't block on them)
    if stage == 2:
        _dispatch_jobs(context, services["workers"])
        set_stage(context, 3)
        stage = 3

    # Stage 3: graceful shutdown
    if stage == 3:
        _shutdown_all(context, services)
        context.state.set("orchestrator_status", "completed")
        return "orchestrator_done"

    _send_ping(context, services["heartbeat"])
    context.wait_for_message()
    return "orchestrator_waiting"


def _got_ping_response(messages: list) -> bool:
    from emergence.common.response import Response

    return any(isinstance(m, Response) and m.success for m in messages)


def _service_pids(context: ProcessContext) -> dict:
    return {
        "heartbeat": context.state.get("svc:heartbeat"),
        "collector": context.state.get("svc:collector"),
        "workers": [
            context.state.get("svc:worker_a"),
            context.state.get("svc:worker_b"),
        ],
    }


def _send_ping(context: ProcessContext, heartbeat_pid: str | None) -> None:
    if heartbeat_pid is None:
        return
    context.mailboxes.send(
        Request(
            sender_pid=str(context.process_id),
            recipient_pid=heartbeat_pid,
            action="ping",
            payload={"round": get_stage(context)},
        )
    )


def _emit_events(context: ProcessContext, collector_pid: str | None) -> None:
    if collector_pid is None:
        return
    topics = ("system.boot", "service.heartbeat", "job.queued")
    for topic in topics:
        context.mailboxes.send(
            Notification(
                sender_pid=str(context.process_id),
                recipient_pid=collector_pid,
                topic=topic,
                data={"phase": 1},
            )
        )


def _dispatch_jobs(
    context: ProcessContext,
    worker_pids: list[str | None],
) -> None:
    jobs = [
        ("job-1", "analyze logs"),
        ("job-2", "compile report"),
    ]
    for i, (job_id, data) in enumerate(jobs):
        pid = worker_pids[i % len(worker_pids)]
        if pid is None:
            continue
        context.mailboxes.send(
            Request(
                sender_pid=str(context.process_id),
                recipient_pid=pid,
                action="process_job",
                payload={"job_id": job_id, "data": data},
            )
        )


def _shutdown_all(context: ProcessContext, services: dict) -> None:
    targets = [services["heartbeat"], services["collector"]]
    targets.extend(services["workers"])
    for pid in targets:
        if pid is None:
            continue
        context.mailboxes.send(
            Request(
                sender_pid=str(context.process_id),
                recipient_pid=pid,
                action="shutdown",
            )
        )
