"""
Tests for emergence.core.event.

Architectural Contract
----------------------
Events are immutable historical facts within EmergenceOS.

These tests protect the following invariants:

* Events are immutable value objects.
* Every event receives a unique EventID.
* Every event receives a timestamp.
* Optional metadata behaves correctly.
* Events serialize into JSON-safe dictionaries.
* Root/non-root events are correctly identified.
* EventType values remain unique.
"""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from emergence.core.event import Event, EventType
from emergence.core.ids import EventID, ProcessID


# ============================================================================
# Construction
# ============================================================================


class TestConstruction:
    """
    Verify Event construction and default values.

    These tests ensure every Event begins life in a valid state.
    """

    def test_minimal_event_construction(self):
        event = Event(event_type=EventType.PROCESS_CREATED)

        assert event.event_type is EventType.PROCESS_CREATED
        assert event.source_process is None
        assert event.correlation_id is None
        assert event.causation_id is None
        assert event.payload == {}

    def test_event_generates_unique_event_id(self):
        event1 = Event(event_type=EventType.PROCESS_CREATED)
        event2 = Event(event_type=EventType.PROCESS_CREATED)

        assert event1.event_id != event2.event_id

    def test_event_generates_timestamp(self):
        event = Event(event_type=EventType.PROCESS_CREATED)

        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo == UTC

    def test_custom_fields_are_preserved(self):
        process_id = ProcessID.new()
        correlation_id = uuid4()
        causation_id = EventID.new()

        payload = {
            "answer": 42,
            "status": "running",
        }

        event = Event(
            event_type=EventType.PROCESS_STARTED,
            source_process=process_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload=payload,
        )

        assert event.source_process == process_id
        assert event.correlation_id == correlation_id
        assert event.causation_id == causation_id
        assert event.payload == payload


# ============================================================================
# Root Events
# ============================================================================


class TestRootEvents:
    """
    Root events begin an event chain.

    Child events always reference a causation event.
    """

    def test_event_without_causation_is_root(self):
        event = Event(event_type=EventType.PROCESS_CREATED)

        assert event.is_root is True

    def test_event_with_causation_is_not_root(self):
        event = Event(
            event_type=EventType.PROCESS_STARTED,
            causation_id=EventID.new(),
        )

        assert event.is_root is False


# ============================================================================
# Serialization
# ============================================================================


class TestSerialization:
    """
    Events must serialize into JSON-safe dictionaries.

    This contract is required for persistence, auditing and replay.
    """

    def test_to_dict_serializes_all_fields(self):
        process_id = ProcessID.new()
        correlation_id = uuid4()
        causation_id = EventID.new()

        payload = {
            "hello": "world",
        }

        event = Event(
            event_type=EventType.PROCESS_STARTED,
            source_process=process_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload=payload,
        )

        result = event.to_dict()

        assert result["event_id"] == str(event.event_id)
        assert result["event_type"] == "process.started"
        assert result["timestamp"] == event.timestamp.isoformat()
        assert result["source_process"] == str(process_id)
        assert result["correlation_id"] == str(correlation_id)
        assert result["causation_id"] == str(causation_id)
        assert result["payload"] == payload

    def test_to_dict_serializes_none_values(self):
        event = Event(event_type=EventType.PROCESS_CREATED)

        result = event.to_dict()

        assert result["source_process"] is None
        assert result["correlation_id"] is None
        assert result["causation_id"] is None
        assert result["payload"] == {}


# ============================================================================
# Immutability
# ============================================================================


class TestImmutability:
    """
    Events are immutable historical facts.

    Once published they must never change.
    """

    def test_event_is_immutable(self):
        event = Event(event_type=EventType.PROCESS_CREATED)

        with pytest.raises(FrozenInstanceError):
            event.event_type = EventType.PROCESS_FAILED


# ============================================================================
# Representation
# ============================================================================


class TestRepresentation:
    """
    repr(Event) should provide useful debugging information.
    """

    def test_repr_contains_core_information(self):
        process_id = ProcessID.new()

        event = Event(
            event_type=EventType.PROCESS_CREATED,
            source_process=process_id,
        )

        representation = repr(event)

        assert "Event(" in representation
        assert str(event.event_id) in representation
        assert "process.created" in representation
        assert str(process_id) in representation


# ============================================================================
# EventType
# ============================================================================


class TestEventType:
    """
    EventType is part of the public kernel API.

    These tests ensure event names remain unique and stable.
    """

    def test_all_event_values_are_unique(self):
        values = [event.value for event in EventType]

        assert len(values) == len(set(values))

    @pytest.mark.parametrize("event_type", list(EventType))
    def test_every_event_type_has_non_empty_string_value(self, event_type):
        assert isinstance(event_type.value, str)
        assert event_type.value != ""

    @pytest.mark.parametrize("event_type", list(EventType))
    def test_event_type_round_trip(self, event_type):
        recreated = EventType(event_type.value)

        assert recreated is event_type


# ============================================================================
# Value Object Behaviour
# ============================================================================


class TestValueObjectBehavior:
    """
    Events behave like immutable dataclass value objects.
    """

    def test_equal_events_compare_equal(self):
        event_id = EventID.new()
        timestamp = datetime.now(UTC)

        event1 = Event(
            event_type=EventType.PROCESS_CREATED,
            event_id=event_id,
            timestamp=timestamp,
        )

        event2 = Event(
            event_type=EventType.PROCESS_CREATED,
            event_id=event_id,
            timestamp=timestamp,
        )

        assert event1 == event2

    def test_events_with_dict_payload_are_not_hashable(self):
        event = Event(event_type=EventType.PROCESS_CREATED)

        with pytest.raises(TypeError):
            {event: "created"}