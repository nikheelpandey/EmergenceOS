from __future__ import annotations

from typing import Any


class MemoryStore:
    """
    Long-term memory for EmergenceOS.

    Unlike the StateStore, MemoryStore persists information across
    process execution and system restarts.

    Future implementations may back this with a database, vector
    store, or distributed storage.
    """

    def __init__(self) -> None:
        self._memory: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a memory value."""
        return self._memory.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Store a memory value."""
        self._memory[key] = value

    def delete(self, key: str) -> None:
        """Delete a memory value."""
        self._memory.pop(key, None)

    def exists(self, key: str) -> bool:
        """Return True if the memory exists."""
        return key in self._memory

    def keys(self) -> list[str]:
        """Return all stored memory keys."""
        return list(self._memory.keys())

    def clear(self) -> None:
        """Clear all memory."""
        self._memory.clear()

    def snapshot(self) -> dict[str, Any]:
        """Return a shallow copy of memory."""
        return self._memory.copy()