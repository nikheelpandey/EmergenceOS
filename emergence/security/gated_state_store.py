from __future__ import annotations

from typing import Any, Callable

from emergence.kernel.state_store import StateStore
from emergence.security.capabilities import STATE_READ, STATE_WRITE
from emergence.security.security_manager import SecurityManager


class GatedStateStore:
    """
    Capability-gated facade over the global StateStore.

  Processes access state exclusively through this wrapper so that
    every read and write is authorized by the SecurityManager.
    """

    def __init__(
        self,
        store: StateStore,
        security: SecurityManager,
        pid: str,
    ) -> None:
        self._store = store
        self._security = security
        self._pid = pid

    def get(self, key: str, default: Any = None) -> Any:
        self._security.require(
            self._pid,
            STATE_READ,
            operation=f"state.get('{key}')",
        )
        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._security.require(
            self._pid,
            STATE_WRITE,
            operation=f"state.set('{key}')",
        )
        self._store.set(key, value)

    def delete(self, key: str) -> None:
        self._security.require(
            self._pid,
            STATE_WRITE,
            operation=f"state.delete('{key}')",
        )
        self._store.delete(key)

    def exists(self, key: str) -> bool:
        self._security.require(
            self._pid,
            STATE_READ,
            operation=f"state.exists('{key}')",
        )
        return self._store.exists(key)

    def keys(self) -> list[str]:
        self._security.require(
            self._pid,
            STATE_READ,
            operation="state.keys()",
        )
        return self._store.keys()

    def watch(
        self,
        key: str,
        callback: Callable[[str, Any], None],
    ) -> None:
        self._security.require(
            self._pid,
            STATE_READ,
            operation=f"state.watch('{key}')",
        )
        self._store.watch(key, callback)

    def unwatch(
        self,
        key: str,
        callback: Callable[[str, Any], None],
    ) -> None:
        self._store.unwatch(key, callback)
