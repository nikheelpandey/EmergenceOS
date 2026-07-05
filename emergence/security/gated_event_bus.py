from __future__ import annotations

from emergence.core.event import Event, EventType
from emergence.events.event_bus import EventBus, EventHandler
from emergence.security.capabilities import EVENT_PUBLISH
from emergence.security.security_manager import SecurityManager


class GatedEventBus:
    """
    Capability-gated facade over the EventBus.

    Processes may publish events only when they hold EVENT_PUBLISH.
    Subscription remains a kernel-internal concern.
    """

    def __init__(
        self,
        bus: EventBus,
        security: SecurityManager,
        pid: str,
    ) -> None:
        self._bus = bus
        self._security = security
        self._pid = pid

    def publish(self, event: Event) -> None:
        self._security.require(
            self._pid,
            EVENT_PUBLISH,
            operation=f"event.publish({event.event_type.value})",
        )
        self._bus.publish(event)

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        self._bus.subscribe(event_type, handler)

    def unsubscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        self._bus.unsubscribe(event_type, handler)
