from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

from emergence.core.event import Event, EventType
from emergence.core.ids import GoalID, ProcessID
from emergence.memory.knowledge_index import infer_artifact_type
from emergence.memory.memory_category import MemoryCategory

if TYPE_CHECKING:
    from emergence.kernel.context import KernelContext


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    """Single human-readable timeline row linked to source events."""

    event_id: str
    event_ids: tuple[str, ...]
    timestamp: datetime
    narrative: str
    event_type: str
    plugin: str | None = None
    scheduled: bool = False


@dataclass(frozen=True, slots=True)
class TimelineDayGroup:
    """Events grouped under a day label."""

    day: str
    entries: tuple[TimelineEntry, ...]


_NARRATABLE_TYPES = frozenset({
    EventType.PROCESS_STARTED,
    EventType.PROCESS_COMPLETED,
    EventType.PROCESS_FAILED,
    EventType.GOAL_CREATED,
    EventType.GOAL_COMPLETED,
    EventType.GOAL_FAILED,
    EventType.GOAL_HEALTH_CHANGED,
    EventType.MEMORY_STORED,
    EventType.TOOL_COMPLETED,
    EventType.TOOL_FAILED,
    EventType.USER_APPROVAL_REQUESTED,
    EventType.USER_APPROVAL_GRANTED,
    EventType.TASK_COMPLETED,
    EventType.CHECKPOINT_CREATED,
    EventType.EVALUATION_COMPLETED,
    EventType.STATE_CHANGED,
})


def narrate_event(event: Event, *, plugin: str | None = None) -> str | None:
    """Translate one event into deterministic human language."""
    plugin_name = _display_name(plugin)
    payload = event.payload

    if event.event_type == EventType.PROCESS_STARTED:
        return f"{plugin_name} started"
    if event.event_type == EventType.PROCESS_COMPLETED:
        return f"{plugin_name} completed"
    if event.event_type == EventType.PROCESS_FAILED:
        error = payload.get("error", "unknown error")
        return f"{plugin_name} failed: {error}"
    if event.event_type == EventType.GOAL_CREATED:
        return f"Goal created: {payload.get('description', 'untitled')}"
    if event.event_type == EventType.GOAL_COMPLETED:
        return "Goal completed"
    if event.event_type == EventType.GOAL_FAILED:
        return "Goal failed"
    if event.event_type == EventType.GOAL_HEALTH_CHANGED:
        health = payload.get("health", "unknown")
        return f"Goal health changed to {health}"
    if event.event_type == EventType.MEMORY_STORED:
        key = _memory_key(event)
        label = _memory_label(key, _memory_category(event))
        return f"{plugin_name} stored {label}"
    if event.event_type == EventType.TOOL_COMPLETED:
        tool = payload.get("tool", payload.get("name", "tool"))
        return f"{plugin_name} completed tool {tool}"
    if event.event_type == EventType.TOOL_FAILED:
        tool = payload.get("tool", payload.get("name", "tool"))
        return f"{plugin_name} tool {tool} failed"
    if event.event_type == EventType.USER_APPROVAL_REQUESTED:
        return f"{plugin_name} requested approval"
    if event.event_type == EventType.USER_APPROVAL_GRANTED:
        return "User approval granted"
    if event.event_type == EventType.TASK_COMPLETED:
        name = payload.get("name", payload.get("task_id", "task"))
        return f"Task completed: {name}"
    if event.event_type == EventType.CHECKPOINT_CREATED:
        return f"{plugin_name} created checkpoint"
    if event.event_type == EventType.EVALUATION_COMPLETED:
        return f"{plugin_name} completed evaluation"
    if event.event_type == EventType.STATE_CHANGED:
        key = str(getattr(event, "key", "") or payload.get("key", ""))
        if key != "pipeline_status":
            return None
        value = getattr(event, "new_value", None)
        if value is None:
            value = payload.get("new_value")
        return f"Pipeline status changed to {value}"

    return None


def build_timeline(
    ctx: KernelContext,
    *,
    goal_id: GoalID | None = None,
    correlation_id: UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a filtered, day-grouped narrative timeline from the event log."""
    events = _filter_events(
        ctx,
        goal_id=goal_id,
        correlation_id=correlation_id,
        since=since,
        until=until,
    )
    entries = _build_entries(events, ctx)
    groups = group_entries_by_day(entries, now=now)
    scheduled = _scheduled_placeholders(ctx, goal_id=goal_id)

    return {
        "goal_id": str(goal_id) if goal_id is not None else None,
        "correlation_id": str(correlation_id) if correlation_id else None,
        "groups": [_group_to_dict(group) for group in groups],
        "scheduled": [_entry_to_dict(entry) for entry in scheduled],
    }


def group_entries_by_day(
    entries: list[TimelineEntry],
    *,
    now: datetime | None = None,
) -> list[TimelineDayGroup]:
    """Group timeline entries under Today / Yesterday / Tomorrow labels."""
    current = now or datetime.now(UTC)
    buckets: dict[str, list[TimelineEntry]] = defaultdict(list)

    for entry in entries:
        label = day_label(entry.timestamp, now=current)
        buckets[label].append(entry)

    order = {"Tomorrow": 0, "Today": 1, "Yesterday": 2}
    labels = sorted(
        buckets.keys(),
        key=lambda label: (order.get(label, 3), label),
    )
    return [
        TimelineDayGroup(day=label, entries=tuple(buckets[label]))
        for label in labels
    ]


def day_label(timestamp: datetime, *, now: datetime) -> str:
    """Map a timestamp to Today, Yesterday, Tomorrow, or ISO date."""
    event_day = timestamp.astimezone(UTC).date()
    today = now.astimezone(UTC).date()
    if event_day == today:
        return "Today"
    if event_day == today - timedelta(days=1):
        return "Yesterday"
    if event_day == today + timedelta(days=1):
        return "Tomorrow"
    return event_day.isoformat()


def _filter_events(
    ctx: KernelContext,
    *,
    goal_id: GoalID | None,
    correlation_id: UUID | None,
    since: datetime | None,
    until: datetime | None,
) -> list[Event]:
    events = ctx.event_store.replay()

    if correlation_id is not None:
        events = [
            event
            for event in events
            if event.correlation_id == correlation_id
        ]

    if since is not None:
        events = [event for event in events if event.timestamp >= since]
    if until is not None:
        events = [event for event in events if event.timestamp <= until]

    if goal_id is None:
        return [event for event in events if event.event_type in _NARRATABLE_TYPES]

    record = ctx.goal_registry.get(goal_id)
    if record is None:
        return []

    process_ids = record.all_process_ids
    filtered: list[Event] = []
    for event in events:
        if event.event_type not in _NARRATABLE_TYPES:
            continue
        if event.source_process is not None and str(event.source_process) in process_ids:
            filtered.append(event)
            continue
        payload_goal = event.payload.get("goal_id")
        if payload_goal is not None and str(payload_goal) == str(goal_id):
            filtered.append(event)
    return filtered


def _build_entries(events: list[Event], ctx: KernelContext) -> list[TimelineEntry]:
    entries: list[TimelineEntry] = []
    memory_batch: list[Event] = []
    batch_plugin: str | None = None
    batch_key: str | None = None
    batch_day: date | None = None

    def flush_memory_batch() -> None:
        nonlocal memory_batch, batch_plugin, batch_key, batch_day
        if not memory_batch:
            return
        entries.append(
            _memory_batch_entry(memory_batch, batch_plugin or "Process")
        )
        memory_batch = []
        batch_plugin = None
        batch_key = None
        batch_day = None

    for event in events:
        if event.event_type == EventType.MEMORY_STORED:
            plugin = _plugin_for_event(event, ctx)
            key = _memory_key(event)
            event_day = event.timestamp.astimezone(UTC).date()
            if (
                memory_batch
                and plugin == batch_plugin
                and key == batch_key
                and event_day == batch_day
            ):
                memory_batch.append(event)
                continue
            flush_memory_batch()
            memory_batch = [event]
            batch_plugin = plugin
            batch_key = key
            batch_day = event_day
            continue

        flush_memory_batch()
        plugin = _plugin_for_event(event, ctx)
        narrative = narrate_event(event, plugin=plugin)
        if narrative is None:
            continue
        entries.append(
            TimelineEntry(
                event_id=str(event.event_id),
                event_ids=(str(event.event_id),),
                timestamp=event.timestamp,
                narrative=narrative,
                event_type=event.event_type.value,
                plugin=plugin,
            )
        )

    flush_memory_batch()
    entries.sort(key=lambda entry: entry.timestamp)
    return entries


def _memory_batch_entry(events: list[Event], plugin: str) -> TimelineEntry:
    first = events[0]
    key = _memory_key(first)
    label = _memory_label(key, _memory_category(first))
    plugin_name = _display_name(plugin)
    count = len(events)

    if count == 1:
        narrative = f"{plugin_name} stored {label}"
    else:
        narrative = f"{plugin_name} stored {count} {label}"

    return TimelineEntry(
        event_id=str(first.event_id),
        event_ids=tuple(str(event.event_id) for event in events),
        timestamp=first.timestamp,
        narrative=narrative,
        event_type=EventType.MEMORY_STORED.value,
        plugin=plugin,
    )


def _scheduled_placeholders(
    ctx: KernelContext,
    *,
    goal_id: GoalID | None,
) -> list[TimelineEntry]:
    """Future scheduled work visible on the goal timeline (M28)."""
    entries: list[TimelineEntry] = []

    for entry in ctx.schedule_manager.pending_all():
        if goal_id is not None and entry.goal_id != goal_id:
            continue
        narrative = f"Scheduled: {entry.description}"
        entries.append(
            TimelineEntry(
                event_id=entry.schedule_id,
                event_ids=(entry.schedule_id,),
                timestamp=entry.fire_at,
                narrative=narrative,
                event_type=EventType.PROCESS_SCHEDULED.value,
                scheduled=True,
            )
        )

    entries.sort(key=lambda item: item.timestamp)
    return entries


def _plugin_for_event(event: Event, ctx: KernelContext) -> str | None:
    source = event.source_process
    if source is None:
        return None
    if ctx.process_table.exists(source):
        return ctx.process_table.get(source).definition.name
    return None


def _memory_key(event: Event) -> str:
    return str(getattr(event, "key", "") or event.payload.get("key", "memory"))


def _memory_category(event: Event) -> MemoryCategory:
    raw = getattr(event, "category", None)
    if raw is None:
        raw = event.payload.get("category", MemoryCategory.WORKING.value)
    if isinstance(raw, MemoryCategory):
        return raw
    return MemoryCategory(str(raw))


def _memory_label(key: str, category: MemoryCategory) -> str:
    artifact_type = infer_artifact_type(key, category)
    mapping = {
        "finding": "findings",
        "report": "report",
        "summary": "summary",
        "document": "document",
        "embedding": "embedding",
        "dataset": "dataset",
    }
    return mapping.get(artifact_type.value, key)


def _display_name(plugin: str | None) -> str:
    if not plugin or plugin == "process":
        return "Process"
    return plugin.replace("_", " ").title()


def _group_to_dict(group: TimelineDayGroup) -> dict[str, Any]:
    return {
        "day": group.day,
        "entries": [_entry_to_dict(entry) for entry in group.entries],
    }


def _entry_to_dict(entry: TimelineEntry) -> dict[str, Any]:
    return {
        "event_id": entry.event_id,
        "event_ids": list(entry.event_ids),
        "timestamp": entry.timestamp.isoformat(),
        "narrative": entry.narrative,
        "event_type": entry.event_type,
        "plugin": entry.plugin,
        "scheduled": entry.scheduled,
    }
