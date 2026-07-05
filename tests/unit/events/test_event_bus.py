"""
Tests for emergence.events.event_bus.

This test suite enforces the EventBus as a deterministic,
synchronous publish-subscribe system.

Key invariants:

- Subscribers are called exactly once per event.
- Delivery order is registration order.
- Exceptions in one handler do not affect others.
- Duplicate subscriptions are ignored.
- Unsubscribe is safe and idempotent.
- Clearing resets all state.
"""

from __future__ import annotations

import pytest

from emergence.events.event_bus import EventBus
from emergence.core.event import Event, EventType





# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def sample_event():
    return Event(event_type=EventType.PROCESS_STARTED)


# ============================================================
# Subscription behavior
# ============================================================

class TestSubscription:
    """
    Validates subscribe/unsubscribe semantics.
    """

    def test_subscribe_adds_handler(self, bus):
        def handler(event): ...

        bus.subscribe(EventType.PROCESS_STARTED, handler)

        assert bus.subscriber_count(EventType.PROCESS_STARTED) == 1

    def test_duplicate_subscription_is_ignored(self, bus):
        def handler(event): ...

        bus.subscribe(EventType.PROCESS_STARTED, handler)
        bus.subscribe(EventType.PROCESS_STARTED, handler)

        assert bus.subscriber_count(EventType.PROCESS_STARTED) == 1

    def test_unsubscribe_removes_handler(self, bus):
        def handler(event): ...

        bus.subscribe(EventType.PROCESS_STARTED, handler)
        bus.unsubscribe(EventType.PROCESS_STARTED, handler)

        assert bus.subscriber_count(EventType.PROCESS_STARTED) == 0

    def test_unsubscribe_nonexistent_is_noop(self, bus):
        def handler(event): ...

        bus.unsubscribe(EventType.PROCESS_STARTED, handler)  # should not crash

        assert bus.subscriber_count(EventType.PROCESS_STARTED) == 0

    def test_has_subscribers(self, bus):
        def handler(event): ...

        assert bus.has_subscribers(EventType.PROCESS_STARTED) is False

        bus.subscribe(EventType.PROCESS_STARTED, handler)

        assert bus.has_subscribers(EventType.PROCESS_STARTED) is True


# ============================================================
# Publish behavior
# ============================================================

class TestPublishing:
    """
    Ensures deterministic event delivery.
    """

    def test_event_delivered_to_single_subscriber(self, bus, sample_event):
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(EventType.PROCESS_STARTED, handler)
        bus.publish(sample_event)

        assert len(received) == 1
        assert received[0] is sample_event

    def test_event_delivered_to_multiple_subscribers(self, bus, sample_event):
        received_a = []
        received_b = []

        def handler_a(event):
            received_a.append(event)

        def handler_b(event):
            received_b.append(event)

        bus.subscribe(EventType.PROCESS_STARTED, handler_a)
        bus.subscribe(EventType.PROCESS_STARTED, handler_b)

        bus.publish(sample_event)

        assert received_a == [sample_event]
        assert received_b == [sample_event]

    def test_no_subscribers_is_noop(self, bus, sample_event):
        # Should not raise
        bus.publish(sample_event)


# ============================================================
# Ordering guarantees
# ============================================================

class TestOrdering:
    """
    Ensures registration order delivery is preserved.
    """

    def test_handlers_called_in_registration_order(self, bus, sample_event):
        order = []

        def handler_a(event):
            order.append("A")

        def handler_b(event):
            order.append("B")

        def handler_c(event):
            order.append("C")

        bus.subscribe(EventType.PROCESS_STARTED, handler_a)
        bus.subscribe(EventType.PROCESS_STARTED, handler_b)
        bus.subscribe(EventType.PROCESS_STARTED, handler_c)

        bus.publish(sample_event)

        assert order == ["A", "B", "C"]


# ============================================================
# Failure isolation
# ============================================================

class TestFailureIsolation:
    """
    One failing handler must not affect others.
    """

    def test_exception_in_one_handler_does_not_stop_delivery(self, bus, sample_event):
        order = []

        def failing_handler(event):
            raise RuntimeError("boom")

        def good_handler(event):
            order.append("OK")

        bus.subscribe(EventType.PROCESS_STARTED, failing_handler)
        bus.subscribe(EventType.PROCESS_STARTED, good_handler)

        bus.publish(sample_event)

        assert order == ["OK"]


# ============================================================
# Idempotency and cleanup
# ============================================================

class TestCleanup:
    """
    Ensures bus can be safely reset.
    """

    def test_clear_removes_all_subscriptions(self, bus):
        def handler(event): ...

        bus.subscribe(EventType.PROCESS_STARTED, handler)
        bus.subscribe(EventType.PROCESS_COMPLETED, handler)

        bus.clear()

        assert len(bus) == 0
        assert bus.has_subscribers(EventType.PROCESS_STARTED) is False

    def test_len_returns_total_subscriptions(self, bus):
        def handler_a(event): ...
        def handler_b(event): ...

        bus.subscribe(EventType.PROCESS_STARTED, handler_a)
        bus.subscribe(EventType.PROCESS_STARTED, handler_b)
        bus.subscribe(EventType.PROCESS_COMPLETED, handler_a)

        assert len(bus) == 3


# ============================================================
# Edge cases
# ============================================================

class TestEdgeCases:
    """
    Boundary conditions and defensive behavior.
    """

    def test_unsubscribe_removes_only_specific_event_type(self, bus):
        def handler(event): ...

        bus.subscribe(EventType.PROCESS_STARTED, handler)
        bus.subscribe(EventType.PROCESS_COMPLETED, handler)

        bus.unsubscribe(EventType.PROCESS_STARTED, handler)

        assert bus.has_subscribers(EventType.PROCESS_STARTED) is False
        assert bus.has_subscribers(EventType.PROCESS_COMPLETED) is True

    def test_handler_modifying_subscription_during_publish_is_safe(self, bus, sample_event):
        def handler(event):
            bus.unsubscribe(EventType.PROCESS_STARTED, handler)

        bus.subscribe(EventType.PROCESS_STARTED, handler)

        # Should not crash due to iteration over copy
        bus.publish(sample_event)

        assert bus.subscriber_count(EventType.PROCESS_STARTED) == 0