"""Unit tests for narrative timeline (M23)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from emergence.core.event import Event, EventType
from emergence.core.ids import GoalID, ProcessID
from emergence.core.process import Process
from emergence.core.process_definition import ProcessDefinition
from emergence.events.memory_events import MemoryStoredEvent
from emergence.events.narrative import (
    build_timeline,
    day_label,
    group_entries_by_day,
    narrate_event,
)
from emergence.kernel.boot_context import create_kernel_context
from emergence.memory.memory_category import MemoryCategory


@pytest.mark.unit
class TestNarrative:
    def test_narrate_memory_stored(self):
        text = narrate_event(
            MemoryStoredEvent(
                key="findings",
                category=MemoryCategory.EPISODIC,
                payload={"key": "findings", "category": "episodic"},
            ),
            plugin="research_assistant",
        )
        assert text == "Research Assistant stored findings"

    def test_narrate_goal_created(self):
        text = narrate_event(
            Event(
                event_type=EventType.GOAL_CREATED,
                payload={"description": "Research Gandhi"},
            )
        )
        assert text == "Goal created: Research Gandhi"

    def test_day_label(self):
        now = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)
        assert day_label(now, now=now) == "Today"
        assert day_label(now - timedelta(days=1), now=now) == "Yesterday"
        assert day_label(now + timedelta(days=1), now=now) == "Tomorrow"

    def test_aggregate_memory_stored_events(self):
        ctx = create_kernel_context()
        goal_id = GoalID.new()
        process_id = ProcessID.new()
        ctx.goal_registry.register(goal_id, "Research")
        ctx.goal_registry.associate_process(goal_id, process_id)

        definition = ProcessDefinition(
            name="research_assistant",
            implementation="research_assistant",
            version="1.0.0",
        )
        ctx.process_table.add(
            Process(definition=definition, process_id=process_id)
        )

        base = datetime(2026, 7, 5, 10, 0, tzinfo=UTC)
        for idx in range(4):
            event = MemoryStoredEvent(
                process_id=process_id,
                key="findings",
                category=MemoryCategory.EPISODIC,
                source_process=process_id,
                payload={"key": "findings", "value": f"finding-{idx}"},
            )
            object.__setattr__(
                event,
                "timestamp",
                base + timedelta(minutes=idx),
            )
            ctx.event_store.append(event)

        timeline = build_timeline(ctx, goal_id=goal_id, now=base)
        entries = timeline["groups"][0]["entries"]
        assert len(entries) == 1
        assert entries[0]["narrative"] == "Research Assistant stored 4 findings"
        assert len(entries[0]["event_ids"]) == 4

    def test_filter_by_correlation_id(self):
        ctx = create_kernel_context()
        correlation = uuid4()
        ctx.event_store.append(
            Event(
                event_type=EventType.GOAL_CREATED,
                correlation_id=correlation,
                payload={"description": "Scoped goal"},
            )
        )
        ctx.event_store.append(
            Event(
                event_type=EventType.GOAL_CREATED,
                payload={"description": "Other goal"},
            )
        )

        timeline = build_timeline(ctx, correlation_id=correlation)
        narratives = [
            entry["narrative"]
            for group in timeline["groups"]
            for entry in group["entries"]
        ]
        assert narratives == ["Goal created: Scoped goal"]

    def test_group_entries_by_day(self):
        from emergence.events.narrative import TimelineEntry

        now = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)
        entries = [
            TimelineEntry(
                event_id="1",
                event_ids=("1",),
                timestamp=now,
                narrative="Today event",
                event_type="goal.created",
            ),
            TimelineEntry(
                event_id="2",
                event_ids=("2",),
                timestamp=now - timedelta(days=1),
                narrative="Yesterday event",
                event_type="goal.created",
            ),
        ]
        groups = group_entries_by_day(entries, now=now)
        assert [group.day for group in groups] == ["Today", "Yesterday"]
