from __future__ import annotations

from typing import TYPE_CHECKING, Any

from emergence.core.event import Event, EventType
from emergence.core.ids import EventID, ProcessID
from emergence.events.narrative import narrate_event

if TYPE_CHECKING:
    from emergence.kernel.context import KernelContext


def inspect_event(ctx: KernelContext, event_id: str) -> dict[str, Any]:
    """Build a structured inspector payload for one event."""
    event = ctx.event_store.get(event_id)
    if event is None:
        raise KeyError(event_id)

    plugin = _plugin_for_event(event, ctx)
    narrative = narrate_event(event, plugin=plugin)

    causation_parent = None
    if event.causation_id is not None:
        parent = ctx.event_store.get(str(event.causation_id))
        if parent is not None:
            causation_parent = _event_summary(parent, ctx)

    correlation_chain: list[dict[str, Any]] = []
    if event.correlation_id is not None:
        for chain_event in ctx.observability.trace.trace(event.correlation_id):
            correlation_chain.append(_event_summary(chain_event, ctx))

    duration_ms = _compute_duration_ms(event, ctx)
    capabilities, required_permissions = _resolve_capabilities(event, ctx)
    goal_id = _resolve_goal_id(event, ctx)
    memory_delta = _memory_delta(event)

    return {
        "event_id": str(event.event_id),
        "event_type": event.event_type.value,
        "timestamp": event.timestamp.isoformat(),
        "narrative": narrative,
        "why": _why_explanation(event, causation_parent),
        "source_process": (
            str(event.source_process) if event.source_process is not None else None
        ),
        "plugin": plugin,
        "capabilities": capabilities,
        "required_permissions": required_permissions,
        "duration_ms": duration_ms,
        "memory_delta": memory_delta,
        "correlation_id": (
            str(event.correlation_id) if event.correlation_id is not None else None
        ),
        "causation_id": (
            str(event.causation_id) if event.causation_id is not None else None
        ),
        "causation_parent": causation_parent,
        "correlation_chain": correlation_chain,
        "goal_id": goal_id,
        "payload": dict(event.payload),
    }


def _event_summary(event: Event, ctx: KernelContext) -> dict[str, Any]:
    plugin = _plugin_for_event(event, ctx)
    return {
        "event_id": str(event.event_id),
        "event_type": event.event_type.value,
        "timestamp": event.timestamp.isoformat(),
        "narrative": narrate_event(event, plugin=plugin),
        "source_process": (
            str(event.source_process) if event.source_process is not None else None
        ),
    }


def _plugin_for_event(event: Event, ctx: KernelContext) -> str | None:
    source = event.source_process
    if source is None:
        return None
    if ctx.process_table.exists(source):
        return ctx.process_table.get(source).definition.name
    return None


def _resolve_goal_id(event: Event, ctx: KernelContext) -> str | None:
    if event.source_process is not None:
        goal_id = ctx.goal_registry.goal_for_process(event.source_process)
        if goal_id is not None:
            return str(goal_id)
    payload_goal = event.payload.get("goal_id")
    return str(payload_goal) if payload_goal is not None else None


def _resolve_capabilities(
    event: Event,
    ctx: KernelContext,
) -> tuple[list[str], list[str]]:
    if event.source_process is None:
        return [], []

    pid = str(event.source_process)
    capabilities = sorted(str(cap) for cap in ctx.capabilities.capabilities(pid))
    required_permissions: list[str] = []
    if ctx.process_table.exists(event.source_process):
        definition = ctx.process_table.get(event.source_process).definition
        required_permissions = sorted(definition.required_permissions)
    return capabilities, required_permissions


def _compute_duration_ms(event: Event, ctx: KernelContext) -> float | None:
    if event.source_process is None:
        return None
    if event.event_type not in {
        EventType.PROCESS_COMPLETED,
        EventType.PROCESS_FAILED,
        EventType.PROCESS_CANCELLED,
    }:
        return None

    process_id = event.source_process
    started_at = None
    for candidate in ctx.event_store.query(source_process=process_id):
        if candidate.event_type == EventType.PROCESS_STARTED:
            started_at = candidate.timestamp
            break

    if started_at is None:
        return None

    delta = (event.timestamp - started_at).total_seconds() * 1000
    return round(delta, 2)


def _memory_delta(event: Event) -> dict[str, Any] | None:
    if event.event_type != EventType.MEMORY_STORED:
        return None
    key = str(getattr(event, "key", "") or event.payload.get("key", ""))
    category = event.payload.get("category")
    value = event.payload.get("value")
    size_bytes = len(str(value).encode("utf-8")) if value is not None else 0
    return {
        "key": key,
        "category": category,
        "size_bytes": size_bytes,
    }


def _why_explanation(
    event: Event,
    causation_parent: dict[str, Any] | None,
) -> str:
    if causation_parent is not None:
        parent_type = causation_parent["event_type"]
        parent_narrative = causation_parent.get("narrative") or parent_type
        return f"Caused by {parent_type}: {parent_narrative}"

    if event.correlation_id is not None:
        return f"Part of correlation chain {event.correlation_id}"

    if event.event_type == EventType.GOAL_CREATED:
        return "User or system submitted a new goal"

    return "Root event with no recorded causation"
