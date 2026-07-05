"""Unit tests for event inspector (M24)."""

from __future__ import annotations

import pytest

from emergence.core.event import Event, EventType
from emergence.core.ids import ProcessID
from emergence.core.process import Process
from emergence.core.process_definition import ProcessDefinition
from emergence.events.memory_events import MemoryStoredEvent
from emergence.kernel.boot_context import create_kernel_context
from emergence.memory.memory_category import MemoryCategory
from emergence.observability.inspector import inspect_event


@pytest.mark.unit
class TestInspector:
    def test_inspect_goal_created_event(self):
        ctx = create_kernel_context()
        event = Event(
            event_type=EventType.GOAL_CREATED,
            payload={"description": "Inspect me"},
        )
        ctx.event_store.append(event)

        payload = inspect_event(ctx, str(event.event_id))
        assert payload["event_type"] == "goal.created"
        assert payload["narrative"] == "Goal created: Inspect me"
        assert payload["why"] == "User or system submitted a new goal"

    def test_inspect_process_duration(self):
        ctx = create_kernel_context()
        process_id = ProcessID.new()
        definition = ProcessDefinition(
            name="worker",
            implementation="worker",
            version="1.0.0",
        )
        ctx.process_table.add(
            Process(definition=definition, process_id=process_id)
        )

        start = Event(
            event_type=EventType.PROCESS_STARTED,
            source_process=process_id,
        )
        complete = Event(
            event_type=EventType.PROCESS_COMPLETED,
            source_process=process_id,
        )
        ctx.event_store.append(start)
        ctx.event_store.append(complete)

        payload = inspect_event(ctx, str(complete.event_id))
        assert payload["duration_ms"] is not None
        assert payload["plugin"] == "worker"

    def test_inspect_memory_stored_delta(self):
        ctx = create_kernel_context()
        event = MemoryStoredEvent(
            key="findings",
            category=MemoryCategory.EPISODIC,
            payload={"key": "findings", "value": "finding text"},
        )
        ctx.event_store.append(event)

        payload = inspect_event(ctx, str(event.event_id))
        assert payload["memory_delta"]["key"] == "findings"
        assert payload["memory_delta"]["size_bytes"] > 0
