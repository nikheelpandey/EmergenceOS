"""
events/event_bus.py

A minimal synchronous Event Bus for EmergenceOS.

The Event Bus is the communication backbone of the operating system.
It is intentionally simple and deterministic.

Responsibilities
----------------
- Register subscribers for specific event types.
- Remove subscribers.
- Publish immutable events.
- Deliver events synchronously in registration order.

Non-Responsibilities
--------------------
- Event persistence
- Event replay
- Retry logic
- Dead-letter queues
- Metrics
- Logging
- Authorization
- Asynchronous execution

These concerns belong to higher-level infrastructure and should not
be implemented here.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, DefaultDict, List

from emergence.core.event import Event, EventType

# ---------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------

EventHandler = Callable[[Event], None]


class EventBus:
    """
    A simple synchronous publish-subscribe event bus.

    Subscribers register callbacks for specific EventTypes.

    Events are delivered:
        - synchronously
        - in registration order
        - to every registered subscriber

    Exceptions raised by one subscriber do not prevent other
    subscribers from receiving the event.
    """

    def __init__(self) -> None:
        self._subscribers: DefaultDict[
            EventType,
            List[EventHandler],
        ] = defaultdict(list)

    # -----------------------------------------------------------------
    # Subscription Management
    # -----------------------------------------------------------------

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        """
        Register a handler for an event type.

        Duplicate registrations are ignored.

        Parameters
        ----------
        event_type:
            Type of event to subscribe to.

        handler:
            Callable that accepts a single Event.
        """
        handlers = self._subscribers[event_type]

        if handler not in handlers:
            handlers.append(handler)

    def unsubscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        """
        Remove a previously registered handler.

        Removing a non-existent handler is a no-op.
        """
        handlers = self._subscribers.get(event_type)

        if handlers is None:
            return

        try:
            handlers.remove(handler)
        except ValueError:
            return

        if not handlers:
            del self._subscribers[event_type]

    # -----------------------------------------------------------------
    # Publishing
    # -----------------------------------------------------------------

    def publish(self, event: Event) -> None:
        """
        Publish an event.

        Every subscriber registered for the event's EventType
        receives the same immutable Event instance.

        Subscriber failures are isolated so that one failing
        subscriber does not prevent delivery to others.
        """
        handlers = self._subscribers.get(event.event_type)

        if not handlers:
            return

        # Iterate over a copy in case subscribers modify
        # subscriptions during event delivery.
        for handler in list(handlers):
            try:
                handler(event)
            except Exception:
                # Future versions may:
                #
                # - emit HandlerFailed events
                # - retry
                # - log
                # - send to dead-letter queue
                #
                # The EventBus intentionally ignores failures.
                pass

    # -----------------------------------------------------------------
    # Introspection
    # -----------------------------------------------------------------

    def has_subscribers(self, event_type: EventType) -> bool:
        """
        Return True if the event type has at least one subscriber.
        """
        return bool(self._subscribers.get(event_type))

    def subscriber_count(self, event_type: EventType) -> int:
        """
        Return the number of subscribers for an event type.
        """
        return len(self._subscribers.get(event_type, []))

    def clear(self) -> None:
        """
        Remove every subscriber from the bus.

        Primarily useful for tests.
        """
        self._subscribers.clear()

    def __len__(self) -> int:
        """
        Return the total number of registered subscriptions.
        """
        return sum(len(handlers) for handlers in self._subscribers.values())