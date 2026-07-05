"""Tests for emergence.events.event_store — M7."""

from __future__ import annotations

from uuid import uuid4

from emergence.core.event import Event, EventType
from emergence.core.ids import ProcessID
from emergence.events.event_store import EventStore
from emergence.events.replay import ReplayEngine
from emergence.events.state_created_event import StateCreatedEvent


class TestEventStore:
    def test_append_and_query(self):
        store = EventStore()
        pid = ProcessID.new()
        cid = uuid4()

        e1 = Event(
            event_type=EventType.PROCESS_CREATED,
            source_process=pid,
            correlation_id=cid,
        )
        e2 = Event(
            event_type=EventType.PROCESS_STARTED,
            source_process=pid,
            correlation_id=cid,
            causation_id=e1.event_id,
        )

        store.append(e1)
        store.append(e2)

        assert store.count() == 2
        chain = store.query(correlation_id=cid)
        assert len(chain) == 2
        assert chain[1].causation_id == e1.event_id

    def test_replay_reconstructs_state(self):
        store = EventStore()
        store.append(
            StateCreatedEvent(key="count", value=1)
        )
        store.append(
            StateCreatedEvent(key="name", value="eos")
        )

        snapshot = ReplayEngine(store).replay()

        assert snapshot.state["count"] == 1
        assert snapshot.state["name"] == "eos"
        assert snapshot.event_count == 2
