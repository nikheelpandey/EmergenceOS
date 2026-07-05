from __future__ import annotations

from typing import Any, Callable

from emergence.events.event_bus import EventBus
from emergence.events.state_changed_event import StateChangedEvent
from emergence.events.state_created_event import StateCreatedEvent
from emergence.events.state_deleted_event import StateDeletedEvent


class StateStore:
    """
    The global shared runtime state of EmergenceOS.

    The StateStore is the single source of truth for all transient system
    state. Every process interacts through this object rather than sharing
    Python objects directly.

    Responsibilities
    ----------------
    - Store key/value pairs
    - Publish state events
    - Notify local watchers
    - Provide snapshots

    Future Responsibilities
    -----------------------
    - Versioning
    - Transactions
    - Persistence
    - Optimistic locking
    - Distributed synchronization
    - State history
    """

    def __init__(self, event_bus: EventBus):
        self._state: dict[str, Any] = {}
        self._watchers: dict[str, list[Callable[[str, Any], None]]] = {}
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from the state store.
        """
        return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Create or update a value.

        Publishes:
            - StateCreatedEvent
            - StateChangedEvent

        Also notifies any local watchers.
        """

        if key in self._state:
            old_value = self._state[key]

            if old_value == value:
                return

            self._state[key] = value

            self._event_bus.publish(
                StateChangedEvent(
                    key=key,
                    old_value=old_value,
                    new_value=value,
                )
            )

        else:
            self._state[key] = value

            self._event_bus.publish(
                StateCreatedEvent(
                    key=key,
                    value=value,
                )
            )

        for callback in self._watchers.get(key, []):
            callback(key, value)

    def delete(self, key: str) -> None:
        """
        Delete a value from the store.

        Publishes:
            - StateDeletedEvent
        """

        if key not in self._state:
            return

        old_value = self._state.pop(key)
        self._watchers.pop(key, None)

        self._event_bus.publish(
            StateDeletedEvent(
                key=key,
                old_value=old_value,
            )
        )

    # ------------------------------------------------------------------
    # Query Helpers
    # ------------------------------------------------------------------

    def exists(self, key: str) -> bool:
        """
        Return True if the key exists.
        """
        return key in self._state

    def keys(self) -> list[str]:
        """
        Return all stored keys.
        """
        return list(self._state.keys())

    def clear(self) -> None:
        """
        Remove all runtime state.

        (No events are emitted yet. We may introduce a
        StateClearedEvent in the future.)
        """
        self._state.clear()

    def snapshot(self) -> dict[str, Any]:
        """
        Return a shallow copy of the current state.

        Useful for:
            - debugging
            - checkpointing
            - inspection
        """
        return self._state.copy()

    # ------------------------------------------------------------------
    # Watchers
    # ------------------------------------------------------------------

    def watch(
        self,
        key: str,
        callback: Callable[[str, Any], None],
    ) -> None:
        """
        Register a callback for changes to a specific key.

        Watchers are lightweight in-process callbacks.

        They are different from EventBus subscribers,
        which are global and asynchronous.
        """
        self._watchers.setdefault(key, []).append(callback)

    def unwatch(
        self,
        key: str,
        callback: Callable[[str, Any], None],
    ) -> None:
        """
        Remove a watcher.
        """

        if key not in self._watchers:
            return

        if callback in self._watchers[key]:
            self._watchers[key].remove(callback)

        if not self._watchers[key]:
            del self._watchers[key]