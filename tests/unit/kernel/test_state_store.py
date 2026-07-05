"""
Tests for emergence.kernel.state_store.StateStore.

This is a core kernel subsystem test suite.

We validate:

- Correct CRUD behavior
- Event emission correctness
- Watcher notification correctness
- Isolation of state
- Idempotent delete behavior
- Snapshot correctness

StateStore is treated as a mini in-memory OS state layer.
"""

from __future__ import annotations

import pytest

from emergence.kernel.state_store import StateStore
from emergence.events.event_bus import EventBus
from emergence.core.event import EventType
from emergence.events.state_created_event import StateCreatedEvent
from emergence.events.state_changed_event import StateChangedEvent
from emergence.events.state_deleted_event import StateDeletedEvent


# ============================================================
# Fake Event Collector
# ============================================================

class EventCollector:
    """
    Captures events emitted via EventBus.
    """

    def __init__(self):
        self.events = []

    def handler(self, event):
        self.events.append(event)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def store(event_bus):
    return StateStore(event_bus)


# ============================================================
# CRUD OPERATIONS
# ============================================================

class TestCRUD:
    """
    Basic state store behavior.
    """

    def test_set_and_get(self, store):
        store.set("a", 1)

        assert store.get("a") == 1

    def test_get_default(self, store):
        assert store.get("missing", 42) == 42

    def test_exists(self, store):
        store.set("x", 10)

        assert store.exists("x") is True
        assert store.exists("y") is False

    def test_keys(self, store):
        store.set("a", 1)
        store.set("b", 2)

        assert set(store.keys()) == {"a", "b"}

    def test_snapshot_is_copy(self, store):
        store.set("a", 1)

        snap = store.snapshot()
        snap["a"] = 999

        assert store.get("a") == 1


# ============================================================
# EVENT EMISSION
# ============================================================

class TestEventEmission:
    """
    Ensures correct event publishing behavior.
    """

    def test_state_created_event_emitted(self, event_bus):
        collector = EventCollector()
        event_bus.subscribe(EventType.STATE_CREATED, collector.handler)

        store = StateStore(event_bus)
        store.set("a", 1)

        assert len(collector.events) == 1
        event = collector.events[0]

        assert isinstance(event, StateCreatedEvent)
        assert event.key == "a"
        assert event.value == 1

    def test_state_changed_event_emitted(self, event_bus):
        collector = EventCollector()
        event_bus.subscribe(EventType.STATE_CHANGED, collector.handler)

        store = StateStore(event_bus)
        store.set("a", 1)
        store.set("a", 2)

        assert len(collector.events) == 1

        event = collector.events[0]

        assert isinstance(event, StateChangedEvent)
        assert event.key == "a"
        assert event.old_value == 1
        assert event.new_value == 2

    def test_set_same_value_is_idempotent(self, event_bus):
        collector = EventCollector()
        event_bus.subscribe(EventType.STATE_CREATED, collector.handler)
        event_bus.subscribe(EventType.STATE_CHANGED, collector.handler)

        store = StateStore(event_bus)
        store.set("a", 1)
        store.set("a", 1)

        assert len(collector.events) == 1
        assert isinstance(collector.events[0], StateCreatedEvent)

    def test_delete_removes_watchers(self, store):
        calls = []

        store.watch("a", lambda key, value: calls.append((key, value)))
        store.set("a", 1)
        store.delete("a")
        store.set("a", 2)

        assert calls == [("a", 1)]

    def test_state_deleted_event_emitted(self, event_bus):
        collector = EventCollector()
        event_bus.subscribe(EventType.STATE_DELETED, collector.handler)

        store = StateStore(event_bus)
        store.set("a", 1)
        store.delete("a")

        assert len(collector.events) == 1

        event = collector.events[0]

        assert isinstance(event, StateDeletedEvent)
        assert event.key == "a"
        assert event.old_value == 1


# ============================================================
# DELETE BEHAVIOR
# ============================================================

class TestDeleteBehavior:
    """
    Ensures safe deletion semantics.
    """

    def test_delete_nonexistent_is_noop(self, store):
        store.delete("missing")  # should not crash

    def test_delete_removes_value(self, store):
        store.set("a", 1)
        store.delete("a")

        assert store.exists("a") is False


# ============================================================
# WATCHERS
# ============================================================

class TestWatchers:
    """
    Ensures local observer system works correctly.
    """

    def test_watch_callback_invoked(self, store):
        calls = []

        def callback(key, value):
            calls.append((key, value))

        store.watch("a", callback)

        store.set("a", 10)

        assert calls == [("a", 10)]

    def test_unwatch_removes_callback(self, store):
        calls = []

        def callback(key, value):
            calls.append((key, value))

        store.watch("a", callback)
        store.unwatch("a", callback)

        store.set("a", 10)

        assert calls == []

    def test_multiple_watchers(self, store):
        calls1 = []
        calls2 = []

        store.watch("a", lambda k, v: calls1.append(v))
        store.watch("a", lambda k, v: calls2.append(v))

        store.set("a", 99)

        assert calls1 == [99]
        assert calls2 == [99]


# ============================================================
# ISOLATION
# ============================================================

class TestIsolation:
    """
    Ensures independent state stores.
    """

    def test_state_is_isolated(self, event_bus):
        store1 = StateStore(event_bus)
        store2 = StateStore(event_bus)

        store1.set("a", 1)

        assert store2.get("a") is None