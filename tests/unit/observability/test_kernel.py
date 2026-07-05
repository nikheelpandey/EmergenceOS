"""Tests for emergence.observability — M9."""

from __future__ import annotations

from uuid import uuid4

from emergence.core.event import Event, EventType
from emergence.core.ids import ProcessID
from emergence.events.event_store import EventStore
from emergence.events.persisting_event_bus import PersistingEventBus
from emergence.observability.kernel import ObservabilityKernel


class TestObservability:
    def test_trace_returns_causal_chain(self):
        store = EventStore()
        bus = PersistingEventBus(store)
        obs = ObservabilityKernel(store, bus)

        pid = ProcessID.new()
        cid = uuid4()
        e1 = Event(
            event_type=EventType.PROCESS_CREATED,
            source_process=pid,
            correlation_id=cid,
        )
        bus.publish(e1)
        e2 = Event(
            event_type=EventType.PROCESS_STARTED,
            source_process=pid,
            correlation_id=cid,
            causation_id=e1.event_id,
        )
        bus.publish(e2)

        chain = obs.trace.trace(cid)
        assert len(chain) == 2
        assert chain[0].event_type == EventType.PROCESS_CREATED

    def test_logger_records_events(self):
        store = EventStore()
        bus = PersistingEventBus(store)
        obs = ObservabilityKernel(store, bus)

        bus.publish(Event(event_type=EventType.KERNEL_STARTED))
        assert len(obs.logger.entries()) >= 1
