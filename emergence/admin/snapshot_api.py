from __future__ import annotations

from datetime import datetime
from typing import Any

from emergence.core.event import EventType
from emergence.core.state import ProcessState
from emergence.kernel.kernel import Kernel
from emergence.observability.snapshot import (
    ProcessSnapshot,
    SystemSnapshot,
    capture_system_snapshot,
)


def build_admin_snapshot(kernel: Kernel) -> dict[str, Any]:
    """
    Build a serializable snapshot of the live kernel for admin clients.
    """
    ctx = kernel.context
    system = capture_system_snapshot(kernel)
    metrics = ctx.observability.metrics.collect(kernel)

    budgets: list[dict[str, Any]] = []
    for process in ctx.process_table.all():
        usage = ctx.budgets.usage(process.process_id)
        budgets.append(
            {
                "process_id": str(process.process_id),
                "name": process.definition.name,
                "tokens": usage.tokens,
                "tool_invocations": usage.tool_invocations,
                "execution_seconds": usage.execution_seconds,
                "retries": usage.retries,
            }
        )

    return {
        "captured_at": system.captured_at.isoformat(),
        "processes": [
            {
                "process_id": process.process_id,
                "name": process.name,
                "state": process.state.value,
                "age_seconds": process.age_seconds,
                "parent_id": process.parent_id,
                "scheduled": process.scheduled,
                "mailbox_pending": process.mailbox_pending,
                "capability_count": process.capability_count,
                "failure_reason": process.failure_reason,
            }
            for process in system.processes
        ],
        "scheduler_depth": system.scheduler_depth,
        "queued_process_ids": list(system.queued_process_ids),
        "state_keys": list(system.state_keys),
        "state": ctx.state.snapshot(),
        "budgets": budgets,
        "metrics": {
            "process_count_by_state": metrics.process_count_by_state,
            "scheduler_depth": metrics.scheduler_depth,
            "event_throughput": metrics.event_throughput,
            "token_consumption": metrics.token_consumption,
            "waiting_count": metrics.waiting_count,
        },
        "pending_approvals": _pending_approvals(kernel),
        "goals": kernel.context.goal_registry.list_views(),
        "os_status": ctx.state.get("os:status"),
    }


def build_goal_payload(kernel: Kernel, goal_id: str) -> dict[str, Any]:
    """Return a single goal view or raise KeyError."""
    from emergence.core.ids import GoalID

    view = kernel.context.goal_registry.query(GoalID(goal_id))
    if view is None:
        raise KeyError(goal_id)
    return view


def build_goal_policy_payload(kernel: Kernel, goal_id: str) -> dict[str, Any]:
    from emergence.core.ids import GoalID

    parsed = GoalID.from_string(goal_id)
    if kernel.context.goal_registry.get(parsed) is None:
        raise KeyError(goal_id)
    usage = kernel.context.goal_registry.policy_usage(parsed)
    if usage is None:
        return {
            "goal_id": goal_id,
            "policy": None,
            "message": "No policy configured for this goal.",
        }
    return {"goal_id": goal_id, **usage}


def build_knowledge_payload(
    kernel: Kernel,
    *,
    goal_id: str | None = None,
    artifact_type: str | None = None,
) -> dict[str, Any]:
    from emergence.core.ids import GoalID
    from emergence.memory.knowledge_index import ArtifactType

    index = kernel.context.knowledge_index
    parsed_goal = GoalID(goal_id) if goal_id else None
    parsed_type = ArtifactType(artifact_type) if artifact_type else None
    artifacts = index.query(
        goal_id=parsed_goal,
        artifact_type=parsed_type,
        include_content=True,
    )
    summary = (
        index.summarize_goal(parsed_goal)
        if parsed_goal is not None
        else None
    )
    return {
        "artifacts": artifacts,
        "summary": summary,
    }


def build_knowledge_artifact_payload(
    kernel: Kernel,
    artifact_id: str,
) -> dict[str, Any]:
    index = kernel.context.knowledge_index
    artifact = index.get(artifact_id)
    if artifact is None:
        raise KeyError(artifact_id)
    return index._to_view(artifact, include_content=True)  # noqa: SLF001


def build_artifacts_payload(
    kernel: Kernel,
    *,
    goal_id: str | None = None,
    artifact_type: str | None = None,
    space_id: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    from emergence.core.ids import GoalID

    service = kernel.context.artifact_service
    parsed_goal = GoalID.from_string(goal_id) if goal_id else None
    artifacts = service.search(
        query=query,
        artifact_type=artifact_type,
        goal_id=parsed_goal,
        space_id=space_id,
        include_content=True,
    )
    summary = (
        service.summarize_goal(parsed_goal)
        if parsed_goal is not None
        else None
    )
    return {
        "artifacts": artifacts,
        "summary": summary,
    }


def build_physical_artifact_payload(
    kernel: Kernel,
    artifact_id: str,
) -> dict[str, Any]:
    service = kernel.context.artifact_service
    record = service.get(artifact_id)
    if record is None:
        raise KeyError(artifact_id)
    return service._to_view(record, include_content=True)  # noqa: SLF001


def build_goal_results_payload(kernel: Kernel, goal_id: str) -> dict[str, Any]:
    """Return report and findings with full content for a goal."""
    from emergence.core.ids import GoalID

    parsed_goal = GoalID.from_string(goal_id)
    if kernel.context.goal_registry.get(parsed_goal) is None:
        raise KeyError(goal_id)

    index = kernel.context.knowledge_index
    artifacts = index.query(goal_id=parsed_goal, include_content=True)
    report = index.primary_report_for_goal(parsed_goal)
    findings = [
        item for item in artifacts if item.get("artifact_type") == "finding"
    ]
    return {
        "goal_id": goal_id,
        "report": report,
        "findings": findings,
        "artifacts": artifacts,
    }


def build_timeline_payload(
    kernel: Kernel,
    *,
    goal_id: str | None = None,
    correlation_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, Any]:
    from uuid import UUID

    from emergence.core.ids import GoalID
    from emergence.events.narrative import build_timeline

    parsed_goal = GoalID.from_string(goal_id) if goal_id else None
    parsed_correlation = UUID(correlation_id) if correlation_id else None
    parsed_since = (
        datetime.fromisoformat(since) if since is not None else None
    )
    parsed_until = (
        datetime.fromisoformat(until) if until is not None else None
    )

    if parsed_goal is not None and kernel.context.goal_registry.get(parsed_goal) is None:
        raise KeyError(goal_id)

    return build_timeline(
        kernel.context,
        goal_id=parsed_goal,
        correlation_id=parsed_correlation,
        since=parsed_since,
        until=parsed_until,
    )


def build_inspect_payload(kernel: Kernel, event_id: str) -> dict[str, Any]:
    from emergence.observability.inspector import inspect_event

    return inspect_event(kernel.context, event_id)


def build_events_payload(
    kernel: Kernel,
    *,
    goal_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    from emergence.core.ids import GoalID
    from emergence.events.narrative import build_timeline

    parsed_goal = GoalID.from_string(goal_id) if goal_id else None
    timeline = build_timeline(kernel.context, goal_id=parsed_goal)
    entries: list[dict[str, Any]] = []
    for group in timeline["groups"]:
        entries.extend(group["entries"])
    entries.sort(key=lambda item: item["timestamp"], reverse=True)
    return {"events": entries[:limit]}


def build_spaces_payload(kernel: Kernel) -> dict[str, Any]:
    return {"spaces": kernel.context.space_registry.list_views()}


def build_space_desktop_payload(kernel: Kernel, space_id: str | None = None) -> dict[str, Any]:
    registry = kernel.context.space_registry
    if space_id is not None:
        registry.switch(space_id)
    return registry.desktop(kernel.context)


def system_snapshot_from_admin(data: dict[str, Any]) -> SystemSnapshot:
    """Rehydrate a SystemSnapshot from an admin API payload."""
    processes = tuple(
        ProcessSnapshot(
            process_id=str(item["process_id"]),
            name=str(item["name"]),
            state=ProcessState(str(item["state"])),
            age_seconds=float(item["age_seconds"]),
            parent_id=(
                str(item["parent_id"])
                if item.get("parent_id") is not None
                else None
            ),
            scheduled=bool(item["scheduled"]),
            mailbox_pending=int(item["mailbox_pending"]),
            capability_count=int(item["capability_count"]),
            failure_reason=(
                str(item["failure_reason"])
                if item.get("failure_reason") is not None
                else None
            ),
        )
        for item in data.get("processes", [])
    )

    captured_raw = data.get("captured_at")
    captured_at = (
        datetime.fromisoformat(str(captured_raw))
        if captured_raw is not None
        else datetime.now()
    )

    return SystemSnapshot(
        captured_at=captured_at,
        processes=processes,
        scheduler_depth=int(data.get("scheduler_depth", 0)),
        queued_process_ids=tuple(
            str(process_id)
            for process_id in data.get("queued_process_ids", [])
        ),
        state_keys=tuple(str(key) for key in data.get("state_keys", [])),
    )


def build_trace_payload(
    kernel: Kernel,
    correlation_id: str,
) -> dict[str, Any]:
    from uuid import UUID

    events = kernel.context.observability.trace.trace(
        UUID(correlation_id)
    )
    return {
        "correlation_id": correlation_id,
        "events": [
            {
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type.value,
                "source_process": (
                    str(event.source_process)
                    if event.source_process
                    else None
                ),
                "payload": event.payload,
            }
            for event in events
        ],
    }


def _pending_approvals(kernel: Kernel) -> list[dict[str, Any]]:
    ctx = kernel.context
    granted = {
        key.removeprefix("approval:")
        for key in ctx.state.keys()
        if key.startswith("approval:") and ctx.state.get(key)
    }

    pending: list[dict[str, Any]] = []
    for event in ctx.event_store.query(
        event_type=EventType.USER_APPROVAL_REQUESTED,
    ):
        request_id = str(event.payload.get("request_id", ""))
        if not request_id or request_id in granted:
            continue
        pending.append(
            {
                "request_id": request_id,
                "message": event.payload.get("message", ""),
                "source_process": (
                    str(event.source_process)
                    if event.source_process
                    else None
                ),
                "timestamp": event.timestamp.isoformat(),
            }
        )
    return pending
