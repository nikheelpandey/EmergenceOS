from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from emergence.core.event import Event, EventType
from emergence.core.ids import EventID, GoalID, ProcessID
from emergence.events.event_bus import EventBus
from emergence.memory.memory_category import MemoryCategory
from emergence.memory.memory_manager import parse_scoped_memory_key
from emergence.spaces.registry import DEFAULT_SPACE_ID

if TYPE_CHECKING:
    from emergence.cognitive.goal_registry import GoalRegistry
    from emergence.events.event_store import EventStore
    from emergence.kernel.context import KernelContext


class ArtifactType(str, Enum):
    """Browsable knowledge artifact categories."""

    DOCUMENT = "document"
    SUMMARY = "summary"
    REPORT = "report"
    EMBEDDING = "embedding"
    DATASET = "dataset"
    FINDING = "finding"


_INDEXED_CATEGORIES = frozenset({
    MemoryCategory.EPISODIC,
    MemoryCategory.SEMANTIC,
})

_TYPE_LABELS: dict[ArtifactType, str] = {
    ArtifactType.DOCUMENT: "docs",
    ArtifactType.SUMMARY: "summaries",
    ArtifactType.REPORT: "reports",
    ArtifactType.EMBEDDING: "embeddings",
    ArtifactType.DATASET: "datasets",
    ArtifactType.FINDING: "findings",
}


def infer_artifact_type(key: str, category: MemoryCategory) -> ArtifactType:
    """Map memory keys and categories to artifact types."""
    normalized = key.lower()

    if "report" in normalized:
        return ArtifactType.REPORT
    if normalized in {"findings", "finding"} or "finding" in normalized:
        return ArtifactType.FINDING
    if "summary" in normalized or "evaluation" in normalized:
        return ArtifactType.SUMMARY
    if "embedding" in normalized or "vector" in normalized:
        return ArtifactType.EMBEDDING
    if "dataset" in normalized or normalized.endswith("_data"):
        return ArtifactType.DATASET
    if category == MemoryCategory.EPISODIC:
        return ArtifactType.FINDING
    return ArtifactType.DOCUMENT


def format_bytes(size: int) -> str:
    """Human-readable byte size."""
    if size >= 1024 * 1024:
        return f"{size // (1024 * 1024)} MB"
    if size >= 1024:
        return f"{size // 1024} KB"
    return f"{size} B"


def format_relative_time(when: datetime | None, *, now: datetime | None = None) -> str:
    """Format a timestamp as a short relative phrase."""
    if when is None:
        return "never"
    current = now or datetime.now(UTC)
    seconds = int((current - when).total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours}h ago"
    days = seconds // 86400
    return f"{days}d ago"


@dataclass(slots=True)
class KnowledgeArtifact:
    """Browsable knowledge derived from a memory store event."""

    artifact_id: str
    goal_id: GoalID | None
    artifact_type: ArtifactType
    key: str
    category: MemoryCategory
    process_id: ProcessID
    plugin: str | None
    size_bytes: int
    stored_at: datetime
    event_id: EventID
    correlation_id: str | None = None
    causation_id: str | None = None
    space_id: str = DEFAULT_SPACE_ID

    @property
    def scoped_key(self) -> str:
        return f"{self.category.value}:{self.process_id}:{self.key}"


@dataclass
class KnowledgeIndex:
    """
    Aggregates MemoryStoredEvent into goal-scoped, typed knowledge artifacts.
    """

    event_bus: EventBus
    _artifacts: dict[str, KnowledgeArtifact] = field(default_factory=dict)
    _by_goal: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    _ctx: KernelContext | None = None

    def bind_context(self, ctx: KernelContext) -> None:
        self._ctx = ctx

    def rebuild_from_event_store(self, event_store: EventStore) -> None:
        """Rebuild the index from persisted memory events."""
        self._artifacts.clear()
        self._by_goal = defaultdict(list)

        for event in event_store.query(event_type=EventType.MEMORY_STORED):
            self._on_memory_stored(event)

    def get(self, artifact_id: str) -> KnowledgeArtifact | None:
        return self._artifacts.get(artifact_id)

    def get_view(self, artifact_id: str) -> dict[str, Any] | None:
        artifact = self.get(artifact_id)
        if artifact is None:
            return None
        return self._to_view(artifact)

    def query(
        self,
        *,
        goal_id: GoalID | None = None,
        artifact_type: ArtifactType | None = None,
        space_id: str | None = None,
        sort: str = "recency",
        include_content: bool = False,
    ) -> list[dict[str, Any]]:
        artifacts = list(self._artifacts.values())

        if goal_id is not None:
            allowed = set(self._by_goal.get(str(goal_id), []))
            artifacts = [item for item in artifacts if item.artifact_id in allowed]

        if space_id is not None:
            artifacts = [item for item in artifacts if item.space_id == space_id]

        if artifact_type is not None:
            artifacts = [
                item for item in artifacts if item.artifact_type == artifact_type
            ]

        if sort == "recency":
            artifacts.sort(key=lambda item: item.stored_at, reverse=True)
        elif sort == "size":
            artifacts.sort(key=lambda item: item.size_bytes, reverse=True)

        return [
            self._to_view(item, include_content=include_content)
            for item in artifacts
        ]

    def read_content(self, artifact: KnowledgeArtifact) -> str | None:
        """Load artifact body from durable memory."""
        ctx = self._ctx
        if ctx is None:
            return None
        value = ctx.memory.peek(
            artifact.process_id,
            artifact.key,
            category=artifact.category,
        )
        if value is None:
            return None
        return str(value)

    def reconcile_from_memory(self) -> None:
        """Index semantic/episodic memory entries missing from the knowledge index."""
        ctx = self._ctx
        if ctx is None:
            return

        for scoped_key, value in ctx.memory.snapshot().items():
            parsed = parse_scoped_memory_key(scoped_key)
            if parsed is None:
                continue
            space_id, category, process_id, key = parsed
            if category not in _INDEXED_CATEGORIES:
                continue

            if self._find_artifact(process_id, key, category) is not None:
                continue

            goal_id = self._goal_for_process(process_id)
            plugin = self._plugin_for_process(process_id)
            size_bytes = len(str(value).encode("utf-8")) if value is not None else 0
            artifact_id = f"memory:{scoped_key}"

            artifact = KnowledgeArtifact(
                artifact_id=artifact_id,
                goal_id=goal_id,
                artifact_type=infer_artifact_type(key, category),
                key=key,
                category=category,
                process_id=process_id,
                plugin=plugin,
                size_bytes=size_bytes,
                stored_at=datetime.now(UTC),
                event_id=EventID.new(),
                space_id=space_id,
            )
            self._artifacts[artifact_id] = artifact
            if goal_id is not None:
                goal_key = str(goal_id)
                if artifact_id not in self._by_goal[goal_key]:
                    self._by_goal[goal_key].append(artifact_id)

    def primary_report_for_goal(self, goal_id: GoalID) -> dict[str, Any] | None:
        """Return the latest report artifact and content for a goal."""
        artifacts = [
            self._artifacts[artifact_id]
            for artifact_id in self._by_goal.get(str(goal_id), [])
            if artifact_id in self._artifacts
        ]
        reports = [
            item for item in artifacts if item.artifact_type == ArtifactType.REPORT
        ]
        if not reports:
            return None
        reports.sort(key=lambda item: item.stored_at, reverse=True)
        report = reports[0]
        return {
            **self._to_view(report, include_content=True),
            "content": self.read_content(report),
        }

    def _find_artifact(
        self,
        process_id: ProcessID,
        key: str,
        category: MemoryCategory,
    ) -> KnowledgeArtifact | None:
        for artifact in self._artifacts.values():
            if (
                artifact.process_id == process_id
                and artifact.key == key
                and artifact.category == category
            ):
                return artifact
        return None

    def summarize_goal(self, goal_id: GoalID) -> dict[str, Any]:
        """Return aggregate knowledge stats for a goal card."""
        artifact_ids = self._by_goal.get(str(goal_id), [])
        artifacts = [
            self._artifacts[artifact_id]
            for artifact_id in artifact_ids
            if artifact_id in self._artifacts
        ]

        counts: dict[str, int] = defaultdict(int)
        total_bytes = 0
        last_updated: datetime | None = None

        for artifact in artifacts:
            counts[artifact.artifact_type.value] += 1
            total_bytes += artifact.size_bytes
            if last_updated is None or artifact.stored_at > last_updated:
                last_updated = artifact.stored_at

        return {
            "total_bytes": total_bytes,
            "total_size": format_bytes(total_bytes),
            "counts_by_type": dict(counts),
            "artifact_count": len(artifacts),
            "last_updated": (
                last_updated.isoformat() if last_updated is not None else None
            ),
            "last_updated_relative": format_relative_time(last_updated),
            "display": self.format_goal_card(total_bytes, counts, last_updated),
        }

    def total_bytes_for_goal(self, goal_id: GoalID) -> int:
        return int(self.summarize_goal(goal_id)["total_bytes"])

    @staticmethod
    def format_goal_card(
        total_bytes: int,
        counts: dict[str, int],
        last_updated: datetime | None,
    ) -> str:
        """Format: '143 MB · 123 docs · 2 reports · updated 2m ago'."""
        parts = [format_bytes(total_bytes)]

        for artifact_type in ArtifactType:
            count = counts.get(artifact_type.value, 0)
            if count <= 0:
                continue
            label = _TYPE_LABELS[artifact_type]
            parts.append(f"{count} {label}")

        parts.append(f"updated {format_relative_time(last_updated)}")
        return " · ".join(parts)

    def snapshot(self) -> dict[str, Any]:
        return {
            "artifacts": [
                {
                    "artifact_id": artifact.artifact_id,
                    "goal_id": (
                        str(artifact.goal_id)
                        if artifact.goal_id is not None
                        else None
                    ),
                    "artifact_type": artifact.artifact_type.value,
                    "key": artifact.key,
                    "category": artifact.category.value,
                    "process_id": str(artifact.process_id),
                    "plugin": artifact.plugin,
                    "size_bytes": artifact.size_bytes,
                    "stored_at": artifact.stored_at.isoformat(),
                    "event_id": str(artifact.event_id),
                    "correlation_id": artifact.correlation_id,
                    "causation_id": artifact.causation_id,
                }
                for artifact in self._artifacts.values()
            ],
        }

    def restore(self, data: dict[str, Any]) -> None:
        self._artifacts.clear()
        self._by_goal = defaultdict(list)

        for raw in data.get("artifacts", []):
            goal_raw = raw.get("goal_id")
            artifact = KnowledgeArtifact(
                artifact_id=str(raw["artifact_id"]),
                goal_id=(
                    GoalID.from_string(str(goal_raw))
                    if goal_raw is not None
                    else None
                ),
                artifact_type=ArtifactType(str(raw["artifact_type"])),
                key=str(raw["key"]),
                category=MemoryCategory(str(raw["category"])),
                process_id=ProcessID.from_string(str(raw["process_id"])),
                plugin=(
                    str(raw["plugin"]) if raw.get("plugin") is not None else None
                ),
                size_bytes=int(raw.get("size_bytes", 0)),
                stored_at=datetime.fromisoformat(str(raw["stored_at"])),
                event_id=EventID.from_string(str(raw["event_id"])),
                correlation_id=raw.get("correlation_id"),
                causation_id=raw.get("causation_id"),
            )
            self._artifacts[artifact.artifact_id] = artifact
            if artifact.goal_id is not None:
                self._by_goal[str(artifact.goal_id)].append(artifact.artifact_id)

    def _to_view(
        self,
        artifact: KnowledgeArtifact,
        *,
        include_content: bool = False,
    ) -> dict[str, Any]:
        view = {
            "artifact_id": artifact.artifact_id,
            "goal_id": (
                str(artifact.goal_id) if artifact.goal_id is not None else None
            ),
            "artifact_type": artifact.artifact_type.value,
            "space_id": artifact.space_id,
            "key": artifact.key,
            "category": artifact.category.value,
            "size_bytes": artifact.size_bytes,
            "stored_at": artifact.stored_at.isoformat(),
            "provenance": {
                "process_id": str(artifact.process_id),
                "plugin": artifact.plugin,
                "event_id": str(artifact.event_id),
                "correlation_id": artifact.correlation_id,
                "causation_id": artifact.causation_id,
            },
        }
        if include_content:
            view["content"] = self.read_content(artifact)
        return view

    def _subscribe(self) -> None:
        self.event_bus.subscribe(EventType.MEMORY_STORED, self._on_memory_stored)
        self.event_bus.subscribe(EventType.MEMORY_DELETED, self._on_memory_deleted)

    def _on_memory_stored(self, event: Event) -> None:
        category = _category_from_event(event)
        if category not in _INDEXED_CATEGORIES:
            return

        process_id = _process_id_from_event(event)
        if process_id is None:
            return

        key = str(getattr(event, "key", "") or event.payload.get("key", ""))
        if not key:
            return

        goal_id = self._goal_for_process(process_id)
        plugin = self._plugin_for_process(process_id)
        space_id = self._space_for_goal(goal_id)
        value = event.payload.get("value")
        size_bytes = len(str(value).encode("utf-8")) if value is not None else 0

        artifact_id = str(event.event_id)
        artifact = KnowledgeArtifact(
            artifact_id=artifact_id,
            goal_id=goal_id,
            artifact_type=infer_artifact_type(key, category),
            key=key,
            category=category,
            process_id=process_id,
            plugin=plugin,
            size_bytes=size_bytes,
            stored_at=event.timestamp,
            event_id=event.event_id,
            correlation_id=(
                str(event.correlation_id)
                if event.correlation_id is not None
                else None
            ),
            causation_id=(
                str(event.causation_id)
                if event.causation_id is not None
                else None
            ),
            space_id=space_id,
        )

        existing = self._artifacts.get(artifact_id)
        if existing is not None and existing.goal_id is not None:
            ids = self._by_goal[existing.goal_id]
            if artifact_id in ids:
                ids.remove(artifact_id)

        self._artifacts[artifact_id] = artifact
        if goal_id is not None:
            goal_key = str(goal_id)
            if artifact_id not in self._by_goal[goal_key]:
                self._by_goal[goal_key].append(artifact_id)

    def _on_memory_deleted(self, event: Event) -> None:
        category = _category_from_event(event)
        if category not in _INDEXED_CATEGORIES:
            return

        matches = [
            artifact
            for artifact in self._artifacts.values()
            if artifact.key == str(
                getattr(event, "key", "") or event.payload.get("key", "")
            )
            and artifact.category == category
            and artifact.process_id == _process_id_from_event(event)
        ]
        for artifact in matches:
            self._artifacts.pop(artifact.artifact_id, None)
            if artifact.goal_id is not None:
                ids = self._by_goal[str(artifact.goal_id)]
                if artifact.artifact_id in ids:
                    ids.remove(artifact.artifact_id)

    def _goal_for_process(self, process_id: ProcessID) -> GoalID | None:
        ctx = self._ctx
        if ctx is None:
            return None
        return ctx.goal_registry.goal_for_process(process_id)

    def _space_for_goal(self, goal_id: GoalID | None) -> str:
        if goal_id is None or self._ctx is None:
            return DEFAULT_SPACE_ID
        record = self._ctx.goal_registry.get(goal_id)
        if record is None:
            return DEFAULT_SPACE_ID
        return record.space_id

    def _plugin_for_process(self, process_id: ProcessID) -> str | None:
        ctx = self._ctx
        if ctx is None or not ctx.process_table.exists(process_id):
            return None
        return ctx.process_table.get(process_id).definition.name


def _category_from_event(event: Event) -> MemoryCategory:
    raw = getattr(event, "category", None)
    if raw is None:
        raw = event.payload.get("category", MemoryCategory.WORKING.value)
    if isinstance(raw, MemoryCategory):
        return raw
    return MemoryCategory(str(raw))


def _process_id_from_event(event: Event) -> ProcessID | None:
    raw = getattr(event, "process_id", None)
    if raw is None:
        payload_raw = event.payload.get("process_id")
        if payload_raw is None and event.source_process is not None:
            return event.source_process
        if payload_raw is None:
            return event.source_process
        raw = payload_raw
    if isinstance(raw, ProcessID):
        return raw
    return ProcessID.from_string(str(raw))


def create_knowledge_index(event_bus: EventBus) -> KnowledgeIndex:
    index = KnowledgeIndex(event_bus=event_bus)
    index._subscribe()  # noqa: SLF001
    return index
