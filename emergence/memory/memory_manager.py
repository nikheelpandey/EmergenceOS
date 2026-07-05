from __future__ import annotations

from typing import Any

from emergence.core.ids import ProcessID
from emergence.events.event_bus import EventBus
from emergence.events.memory_events import (
    MemoryDeletedEvent,
    MemoryRetrievedEvent,
    MemoryStoredEvent,
)
from emergence.memory.memory_category import MemoryCategory
from emergence.memory.memory_store import MemoryStore
from emergence.memory.vector_index import VectorIndex
from emergence.spaces.registry import DEFAULT_SPACE_ID


def _scoped_key(
    process_id: ProcessID,
    category: MemoryCategory,
    key: str,
    *,
    space_id: str = DEFAULT_SPACE_ID,
) -> str:
    return f"{space_id}:{category.value}:{process_id}:{key}"


def _scoped_key_candidates(
    process_id: ProcessID,
    category: MemoryCategory,
    key: str,
    *,
    space_id: str = DEFAULT_SPACE_ID,
) -> tuple[str, ...]:
    """Return scoped key variants (new space-prefixed and legacy)."""
    legacy = f"{category.value}:{process_id}:{key}"
    scoped = _scoped_key(process_id, category, key, space_id=space_id)
    if legacy == scoped:
        return (scoped,)
    return (scoped, legacy)


def parse_scoped_memory_key(
    scoped_key: str,
) -> tuple[str, MemoryCategory, ProcessID, str] | None:
    """Parse a memory store key into space, category, process, and short key."""
    parts = scoped_key.split(":", 3)
    try:
        if len(parts) == 4:
            space_id, category_raw, process_raw, short_key = parts
            return (
                space_id,
                MemoryCategory(category_raw),
                ProcessID.from_string(process_raw),
                short_key,
            )
        if len(parts) == 3:
            category_raw, process_raw, short_key = parts
            return (
                DEFAULT_SPACE_ID,
                MemoryCategory(category_raw),
                ProcessID.from_string(process_raw),
                short_key,
            )
    except (ValueError, TypeError):
        return None
    return None


class MemoryManager:
    """
    Central owner of long-term memory.

    Processes never access MemoryStore directly — all operations
    flow through this manager and produce observable events.
    """

    def __init__(
        self,
        store: MemoryStore,
        event_bus: EventBus,
    ) -> None:
        self._store = store
        self._event_bus = event_bus
        self._index = VectorIndex()
        self._space_resolver: Any | None = None

    def bind_space_resolver(self, resolver) -> None:
        """Resolve space_id from a process_id for scoped memory keys."""
        self._space_resolver = resolver

    def _resolve_space(self, process_id: ProcessID) -> str:
        if self._space_resolver is not None:
            return self._space_resolver(process_id)
        return DEFAULT_SPACE_ID

    def store(
        self,
        process_id: ProcessID,
        key: str,
        value: Any,
        *,
        category: MemoryCategory = MemoryCategory.WORKING,
    ) -> None:
        scoped = _scoped_key(
            process_id,
            category,
            key,
            space_id=self._resolve_space(process_id),
        )
        self._store.set(scoped, value)
        if category in (MemoryCategory.EPISODIC, MemoryCategory.SEMANTIC):
            self._index.add(
                scoped,
                str(value),
                metadata={
                    "process_id": str(process_id),
                    "key": key,
                    "category": category.value,
                },
            )
        self._event_bus.publish(
            MemoryStoredEvent(
                process_id=process_id,
                key=key,
                category=category,
                source_process=process_id,
                payload={"value": value},
            )
        )

    def peek(
        self,
        process_id: ProcessID,
        key: str,
        *,
        category: MemoryCategory = MemoryCategory.WORKING,
        default: Any = None,
    ) -> Any:
        """Read memory without emitting a retrieval event."""
        space_id = self._resolve_space(process_id)
        for scoped in _scoped_key_candidates(
            process_id,
            category,
            key,
            space_id=space_id,
        ):
            if self._store.exists(scoped):
                return self._store.get(scoped, default)
        return default

    def snapshot(self) -> dict[str, Any]:
        """Return all scoped memory entries."""
        return self._store.snapshot()

    def retrieve(
        self,
        process_id: ProcessID,
        key: str,
        *,
        category: MemoryCategory = MemoryCategory.WORKING,
        default: Any = None,
    ) -> Any:
        space_id = self._resolve_space(process_id)
        for scoped in _scoped_key_candidates(
            process_id,
            category,
            key,
            space_id=space_id,
        ):
            if self._store.exists(scoped):
                value = self._store.get(scoped, default)
                break
        else:
            value = default
        self._event_bus.publish(
            MemoryRetrievedEvent(
                process_id=process_id,
                key=key,
                category=category,
                source_process=process_id,
            )
        )
        return value

    def delete(
        self,
        process_id: ProcessID,
        key: str,
        *,
        category: MemoryCategory = MemoryCategory.WORKING,
    ) -> None:
        space_id = self._resolve_space(process_id)
        for scoped in _scoped_key_candidates(
            process_id,
            category,
            key,
            space_id=space_id,
        ):
            if self._store.exists(scoped):
                self._store.delete(scoped)
                self._index.remove(scoped)
                break
        self._event_bus.publish(
            MemoryDeletedEvent(
                process_id=process_id,
                key=key,
                category=category,
                source_process=process_id,
            )
        )

    def exists(
        self,
        process_id: ProcessID,
        key: str,
        *,
        category: MemoryCategory = MemoryCategory.WORKING,
    ) -> bool:
        space_id = self._resolve_space(process_id)
        return any(
            self._store.exists(scoped)
            for scoped in _scoped_key_candidates(
                process_id,
                category,
                key,
                space_id=space_id,
            )
        )

    def working_snapshot(self, process_id: ProcessID) -> dict[str, Any]:
        """Return all working-memory entries for a process."""
        space_id = self._resolve_space(process_id)
        prefixes = (
            f"{space_id}:{MemoryCategory.WORKING.value}:{process_id}:",
            f"{MemoryCategory.WORKING.value}:{process_id}:",
        )
        result: dict[str, Any] = {}
        for scoped_key in self._store.keys():
            for prefix in prefixes:
                if scoped_key.startswith(prefix):
                    short_key = scoped_key[len(prefix):]
                    result[short_key] = self._store.get(scoped_key)
                    break
        return result

    def search(
        self,
        process_id: ProcessID,
        query: str,
        *,
        categories: list[MemoryCategory] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search episodic and semantic memory via the vector index.

        Results are scoped to the requesting process.
        """
        if categories is None:
            categories = [
                MemoryCategory.EPISODIC,
                MemoryCategory.SEMANTIC,
            ]

        space_id = self._resolve_space(process_id)
        prefix_parts = [
            f"{space_id}:{cat.value}:{process_id}:"
            for cat in categories
        ]
        prefix_parts.extend(
            f"{cat.value}:{process_id}:"
            for cat in categories
        )

        hits = self._index.search(query, top_k=top_k * 3)
        results: list[dict[str, Any]] = []

        for hit in hits:
            if not any(hit.key.startswith(p) for p in prefix_parts):
                continue

            meta = hit.metadata
            results.append({
                "key": meta.get("key", hit.key),
                "category": meta.get("category", ""),
                "text": hit.text,
                "score": round(hit.score, 4),
            })
            if len(results) >= top_k:
                break

        self._event_bus.publish(
            MemoryRetrievedEvent(
                process_id=process_id,
                key=f"search:{query[:40]}",
                category=MemoryCategory.SEMANTIC,
                source_process=process_id,
                payload={"query": query, "count": len(results)},
            )
        )
        return results

    def knowledge_size_bytes(self, process_ids: set[str]) -> int:
        """Approximate byte size of episodic/semantic memory for processes."""
        prefix_parts = [f":{pid}:" for pid in process_ids]
        total = 0
        for key in self._store.keys():
            if not any(part in key for part in prefix_parts):
                continue
            value = self._store.get(key)
            if value is not None:
                total += len(str(value).encode("utf-8"))
        return total
