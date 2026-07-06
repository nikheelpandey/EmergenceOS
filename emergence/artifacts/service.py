from __future__ import annotations

import mimetypes
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from emergence.events.event_bus import EventBus
from emergence.core.ids import ArtifactID, GoalID, ProcessID
from emergence.events.artifact_events import (
    ArtifactCreatedEvent,
    ArtifactDeletedEvent,
    ArtifactUpdatedEvent,
    artifact_event_payload,
)
from emergence.memory.knowledge_index import format_bytes, format_relative_time
from emergence.spaces.registry import DEFAULT_SPACE_ID

if TYPE_CHECKING:
    from emergence.kernel.context import KernelContext


class ArtifactStatus(str, Enum):
    """Lifecycle status for a physical artifact."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DELETED = "deleted"


@dataclass(slots=True)
class ArtifactRecord:
    """A durable, queryable physical artifact."""

    artifact_id: ArtifactID
    name: str
    artifact_type: str
    owner_goal_id: GoalID | None
    owner_process_id: ProcessID | None
    space_id: str
    version: int
    status: ArtifactStatus
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    mime_type: str | None = None
    size_bytes: int = 0
    storage_key: str = ""
    knowledge_links: list[str] = field(default_factory=list)
    links: dict[str, list[str]] = field(default_factory=dict)

    @property
    def lineage_id(self) -> str:
        """Stable identity across versions (artifact_id for v1 lineage)."""
        return str(self.provenance.get("lineage_id") or self.artifact_id)


@dataclass
class ArtifactService:
    """
    Kernel primitive for durable, typed, queryable physical artifacts.

    Knowledge holds semantic facts; artifacts hold physical outputs
    (PDFs, images, datasets, codebases, etc.) with provenance and
    versioning. All mutations emit events for event-driven workflows.
    """

    event_bus: EventBus
    _records: dict[str, ArtifactRecord] = field(default_factory=dict)
    _by_goal: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _by_type: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _by_lineage: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _referenced_by: dict[str, set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    _watches: list[dict[str, Any]] = field(default_factory=list)
    _pending_notifications: set[str] = field(default_factory=set)
    _blob_root: Path | None = None
    _ctx: KernelContext | None = None

    def bind_context(self, ctx: KernelContext) -> None:
        self._ctx = ctx

    @property
    def blob_root(self) -> Path:
        if self._blob_root is None:
            from emergence.admin.paths import data_dir

            self._blob_root = data_dir() / "artifacts"
        return self._blob_root

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        name: str,
        artifact_type: str,
        content: str | bytes,
        owner_process_id: ProcessID | None = None,
        owner_goal_id: GoalID | None = None,
        space_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        mime_type: str | None = None,
        based_on: ArtifactID | str | None = None,
        knowledge_links: list[str] | None = None,
    ) -> ArtifactRecord:
        """Create a new artifact at version 1."""
        if not name.strip():
            raise ValueError("name is required")
        if not artifact_type.strip():
            raise ValueError("artifact_type is required")

        resolved_space = space_id or self._space_for_process(owner_process_id)
        resolved_goal = owner_goal_id or self._goal_for_process(owner_process_id)
        artifact_id = ArtifactID.new()
        now = datetime.now(UTC)

        record = ArtifactRecord(
            artifact_id=artifact_id,
            name=name.strip(),
            artifact_type=artifact_type.strip().lower(),
            owner_goal_id=resolved_goal,
            owner_process_id=owner_process_id,
            space_id=resolved_space,
            version=1,
            status=ArtifactStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            metadata=dict(metadata or {}),
            provenance=self._build_provenance(
                provenance,
                owner_process_id=owner_process_id,
                based_on=based_on,
                lineage_id=str(artifact_id),
            ),
            tags=[tag.strip().lower() for tag in (tags or []) if tag.strip()],
            mime_type=mime_type or _guess_mime_type(name),
            knowledge_links=list(knowledge_links or []),
        )
        record.size_bytes = self._write_blob(record, content)
        record.storage_key = self._storage_key(record)

        self._index_record(record)
        self._publish_created(record)
        return record

    def update(
        self,
        artifact_id: ArtifactID | str,
        *,
        content: str | bytes,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        owner_process_id: ProcessID | None = None,
    ) -> ArtifactRecord:
        """Create a new version of an existing artifact."""
        current = self._require_active(artifact_id)
        current.status = ArtifactStatus.SUPERSEDED

        now = datetime.now(UTC)
        new_version = current.version + 1
        new_id = ArtifactID.new()

        record = ArtifactRecord(
            artifact_id=new_id,
            name=(name or current.name).strip(),
            artifact_type=current.artifact_type,
            owner_goal_id=current.owner_goal_id,
            owner_process_id=owner_process_id or current.owner_process_id,
            space_id=current.space_id,
            version=new_version,
            status=ArtifactStatus.ACTIVE,
            created_at=current.created_at,
            updated_at=now,
            metadata={**current.metadata, **(metadata or {})},
            provenance={
                **current.provenance,
                "previous_artifact_id": str(current.artifact_id),
                "previous_version": current.version,
                "updated_by_process": (
                    str(owner_process_id)
                    if owner_process_id is not None
                    else current.provenance.get("updated_by_process")
                ),
                "lineage_id": current.lineage_id,
            },
            tags=(
                [tag.strip().lower() for tag in tags if tag.strip()]
                if tags is not None
                else list(current.tags)
            ),
            mime_type=current.mime_type,
            knowledge_links=list(current.knowledge_links),
            links={key: list(values) for key, values in current.links.items()},
        )
        record.size_bytes = self._write_blob(record, content)
        record.storage_key = self._storage_key(record)

        self._index_record(record)
        self._publish_updated(record, previous_version=current.version)
        return record

    def delete(self, artifact_id: ArtifactID | str) -> ArtifactRecord:
        """Soft-delete the active version of an artifact."""
        record = self._require_active(artifact_id)
        record.status = ArtifactStatus.DELETED
        record.updated_at = datetime.now(UTC)
        self._publish_deleted(record)
        return record

    def link(
        self,
        artifact_id: ArtifactID | str,
        target_id: str,
        *,
        link_type: str = "related",
    ) -> ArtifactRecord:
        """Link two artifacts (e.g. resume → application)."""
        record = self._require_active(artifact_id)
        if not target_id.strip():
            raise ValueError("target_id is required")

        bucket = record.links.setdefault(link_type, [])
        if target_id not in bucket:
            bucket.append(target_id)
        self._referenced_by[target_id].add(str(record.artifact_id))
        record.updated_at = datetime.now(UTC)
        return record

    def register_watch(
        self,
        process_id: ProcessID,
        *,
        artifact_id: str | None = None,
        artifact_type: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Register a process to be notified on matching artifact events."""
        entry = {
            "process_id": str(process_id),
            "artifact_id": artifact_id,
            "artifact_type": (
                artifact_type.strip().lower() if artifact_type else None
            ),
            "tags": [tag.strip().lower() for tag in (tags or [])],
        }
        self._watches.append(entry)
        return {"watching": True, **entry}

    def consume_notification(self, process_id: ProcessID) -> bool:
        """Return True once if an artifact event matched this process."""
        key = str(process_id)
        if key in self._pending_notifications:
            self._pending_notifications.discard(key)
            return True
        return False

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get(
        self,
        artifact_id: ArtifactID | str,
        *,
        version: int | None = None,
    ) -> ArtifactRecord | None:
        if version is not None:
            lineage = self._lineage_for(str(artifact_id))
            if lineage is None:
                return None
            for record_id in self._by_lineage[lineage]:
                record = self._records[record_id]
                if record.version == version:
                    return record
            return None

        return self._records.get(str(artifact_id))

    def read_content(
        self,
        artifact_id: ArtifactID | str,
        *,
        version: int | None = None,
    ) -> bytes | None:
        record = self.get(artifact_id, version=version)
        if record is None:
            return None
        path = self._blob_path(record)
        if not path.exists():
            return None
        return path.read_bytes()

    def search(
        self,
        *,
        query: str | None = None,
        artifact_type: str | None = None,
        goal_id: GoalID | None = None,
        space_id: str | None = None,
        tags: list[str] | None = None,
        latest_only: bool = True,
        status: ArtifactStatus | None = ArtifactStatus.ACTIVE,
        limit: int = 50,
        include_content: bool = False,
    ) -> list[dict[str, Any]]:
        records = list(self._records.values())

        if status is not None:
            records = [item for item in records if item.status == status]

        if goal_id is not None:
            allowed = set(self._by_goal.get(str(goal_id), []))
            records = [item for item in records if str(item.artifact_id) in allowed]

        if space_id is not None:
            records = [item for item in records if item.space_id == space_id]

        if artifact_type is not None:
            normalized = artifact_type.strip().lower()
            records = [item for item in records if item.artifact_type == normalized]

        if tags:
            required = {tag.strip().lower() for tag in tags}
            records = [
                item
                for item in records
                if required.issubset(set(item.tags))
            ]

        if latest_only:
            records = self._latest_versions(records)

        if query:
            records = self._rank_by_query(records, query.strip().lower())

        records.sort(key=lambda item: item.updated_at, reverse=True)
        records = records[:limit]

        return [
            self._to_view(item, include_content=include_content)
            for item in records
        ]

    def versions(self, artifact_id: ArtifactID | str) -> list[dict[str, Any]]:
        lineage = self._lineage_for(str(artifact_id))
        if lineage is None:
            return []

        items = [
            self._records[record_id]
            for record_id in self._by_lineage[lineage]
            if record_id in self._records
        ]
        items.sort(key=lambda item: item.version)
        return [self._to_view(item) for item in items]

    def export(
        self,
        artifact_id: ArtifactID | str,
        *,
        version: int | None = None,
    ) -> dict[str, Any]:
        record = self.get(artifact_id, version=version)
        if record is None:
            raise KeyError(f"artifact not found: {artifact_id}")
        if version is None and record.status != ArtifactStatus.ACTIVE:
            resolved = self._active_in_lineage(record.lineage_id)
            if resolved is not None:
                record = resolved

        content = self.read_content(record.artifact_id, version=record.version)
        if content is None:
            raise FileNotFoundError(
                f"artifact content missing: {record.artifact_id}"
            )

        try:
            text = content.decode("utf-8")
            binary = False
        except UnicodeDecodeError:
            text = content.decode("latin-1")
            binary = True

        return {
            **self._to_view(record, include_content=False),
            "content": text,
            "binary": binary,
            "export_path": record.storage_key,
        }

    def summarize_goal(self, goal_id: GoalID) -> dict[str, Any]:
        artifact_ids = self._by_goal.get(str(goal_id), [])
        records = [
            self._records[artifact_id]
            for artifact_id in artifact_ids
            if artifact_id in self._records
            and self._records[artifact_id].status == ArtifactStatus.ACTIVE
        ]
        records = self._latest_versions(records)

        counts: dict[str, int] = defaultdict(int)
        total_bytes = 0
        last_updated: datetime | None = None

        for record in records:
            counts[record.artifact_type] += 1
            total_bytes += record.size_bytes
            if last_updated is None or record.updated_at > last_updated:
                last_updated = record.updated_at

        return {
            "artifact_count": len(records),
            "total_bytes": total_bytes,
            "total_size": format_bytes(total_bytes),
            "counts_by_type": dict(counts),
            "last_updated": (
                last_updated.isoformat() if last_updated is not None else None
            ),
            "last_updated_relative": format_relative_time(last_updated),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return {
            "artifacts": [
                self._serialize_record(record)
                for record in self._records.values()
            ],
            "watches": list(self._watches),
        }

    def restore(self, data: dict[str, Any]) -> None:
        self._records.clear()
        self._by_goal = defaultdict(list)
        self._by_type = defaultdict(list)
        self._by_lineage = defaultdict(list)
        self._referenced_by = defaultdict(set)
        self._watches = list(data.get("watches", []))

        for raw in data.get("artifacts", []):
            record = self._deserialize_record(raw)
            self._index_record(record, reindex=False)

        self._rebuild_reference_index()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _require_active(self, artifact_id: ArtifactID | str) -> ArtifactRecord:
        record = self._records.get(str(artifact_id))
        if record is None:
            raise KeyError(f"artifact not found: {artifact_id}")
        if record.status != ArtifactStatus.ACTIVE:
            raise ValueError(f"artifact is not active: {artifact_id}")
        return record

    def _index_record(self, record: ArtifactRecord, *, reindex: bool = True) -> None:
        key = str(record.artifact_id)
        self._records[key] = record

        if reindex:
            if record.owner_goal_id is not None:
                goal_key = str(record.owner_goal_id)
                if key not in self._by_goal[goal_key]:
                    self._by_goal[goal_key].append(key)

            if key not in self._by_type[record.artifact_type]:
                self._by_type[record.artifact_type].append(key)

            lineage = record.lineage_id
            if key not in self._by_lineage[lineage]:
                self._by_lineage[lineage].append(key)

    def _rebuild_reference_index(self) -> None:
        self._referenced_by = defaultdict(set)
        for record in self._records.values():
            for targets in record.links.values():
                for target_id in targets:
                    self._referenced_by[target_id].add(str(record.artifact_id))

    def _latest_versions(self, records: list[ArtifactRecord]) -> list[ArtifactRecord]:
        latest: dict[str, ArtifactRecord] = {}
        for record in records:
            lineage = record.lineage_id
            current = latest.get(lineage)
            if current is None or record.version > current.version:
                latest[lineage] = record
        return list(latest.values())

    def _rank_by_query(
        self,
        records: list[ArtifactRecord],
        query: str,
    ) -> list[ArtifactRecord]:
        if not query:
            return records

        scored: list[tuple[int, ArtifactRecord]] = []
        tokens = [token for token in re.split(r"\s+", query) if token]

        for record in records:
            haystacks = [
                record.name.lower(),
                record.artifact_type.lower(),
                " ".join(record.tags),
                " ".join(str(value) for value in record.metadata.values()).lower(),
            ]
            score = 0
            blob = " ".join(haystacks)
            if query in blob:
                score += 5
            for token in tokens:
                if token in blob:
                    score += 2
                if token in record.name.lower():
                    score += 3
                if token in record.tags:
                    score += 2
            if score > 0:
                scored.append((score, record))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [record for _, record in scored]

    def _lineage_for(self, artifact_id: str) -> str | None:
        record = self._records.get(artifact_id)
        if record is None:
            return None
        return record.lineage_id

    def _active_in_lineage(self, lineage_id: str) -> ArtifactRecord | None:
        candidates = [
            self._records[record_id]
            for record_id in self._by_lineage.get(lineage_id, [])
            if record_id in self._records
            and self._records[record_id].status == ArtifactStatus.ACTIVE
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda item: item.version, reverse=True)
        return candidates[0]

    def _build_provenance(
        self,
        provenance: dict[str, Any] | None,
        *,
        owner_process_id: ProcessID | None,
        based_on: ArtifactID | str | None,
        lineage_id: str,
    ) -> dict[str, Any]:
        result = dict(provenance or {})
        if owner_process_id is not None:
            result.setdefault("created_by_process", str(owner_process_id))
            plugin = self._plugin_for_process(owner_process_id)
            if plugin is not None:
                result.setdefault("created_by_plugin", plugin)
        if based_on is not None:
            result["based_on_artifact_id"] = str(based_on)
            parent = self._records.get(str(based_on))
            if parent is not None:
                result.setdefault("based_on_name", parent.name)
        result.setdefault("lineage_id", lineage_id)
        return result

    def _write_blob(self, record: ArtifactRecord, content: str | bytes) -> int:
        from emergence.admin.paths import data_dir

        data_dir().mkdir(parents=True, exist_ok=True)
        path = self._blob_path(record)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = content.encode("utf-8") if isinstance(content, str) else content
        path.write_bytes(data)
        return len(data)

    def _blob_path(self, record: ArtifactRecord) -> Path:
        return (
            self.blob_root
            / record.space_id
            / record.lineage_id
            / f"v{record.version}"
            / _safe_filename(record.name)
        )

    def _storage_key(self, record: ArtifactRecord) -> str:
        from emergence.admin.paths import data_dir

        return str(self._blob_path(record).relative_to(data_dir()))

    def _publish_created(self, record: ArtifactRecord) -> None:
        payload = artifact_event_payload(record)
        self.event_bus.publish(
            ArtifactCreatedEvent(
                artifact_id=record.artifact_id,
                artifact_type=record.artifact_type,
                name=record.name,
                version=record.version,
                goal_id=record.owner_goal_id,
                space_id=record.space_id,
                source_process=record.owner_process_id,
                payload=payload,
            )
        )
        self._notify_watchers(record)

    def _publish_updated(
        self,
        record: ArtifactRecord,
        *,
        previous_version: int,
    ) -> None:
        payload = artifact_event_payload(
            record,
            extra={"previous_version": previous_version},
        )
        self.event_bus.publish(
            ArtifactUpdatedEvent(
                artifact_id=record.artifact_id,
                artifact_type=record.artifact_type,
                name=record.name,
                version=record.version,
                previous_version=previous_version,
                goal_id=record.owner_goal_id,
                space_id=record.space_id,
                source_process=record.owner_process_id,
                payload=payload,
            )
        )
        self._notify_watchers(record)

    def _publish_deleted(self, record: ArtifactRecord) -> None:
        payload = artifact_event_payload(record)
        self.event_bus.publish(
            ArtifactDeletedEvent(
                artifact_id=record.artifact_id,
                artifact_type=record.artifact_type,
                name=record.name,
                goal_id=record.owner_goal_id,
                space_id=record.space_id,
                source_process=record.owner_process_id,
                payload=payload,
            )
        )
        self._notify_watchers(record)

    def _notify_watchers(self, record: ArtifactRecord) -> None:
        for watch in self._watches:
            if watch.get("artifact_id") not in {None, str(record.artifact_id)}:
                lineage_matches = any(
                    str(record.artifact_id) == record_id
                    for record_id in self._by_lineage.get(record.lineage_id, [])
                )
                if not lineage_matches and watch["artifact_id"] != record.lineage_id:
                    continue
            if (
                watch.get("artifact_type") is not None
                and watch["artifact_type"] != record.artifact_type
            ):
                continue
            required_tags = set(watch.get("tags") or [])
            if required_tags and not required_tags.issubset(set(record.tags)):
                continue
            self._pending_notifications.add(str(watch["process_id"]))

    def _to_view(
        self,
        record: ArtifactRecord,
        *,
        include_content: bool = False,
    ) -> dict[str, Any]:
        referenced_by = sorted(self._referenced_by.get(str(record.artifact_id), set()))
        view = {
            "artifact_id": str(record.artifact_id),
            "name": record.name,
            "artifact_type": record.artifact_type,
            "owner_goal_id": (
                str(record.owner_goal_id)
                if record.owner_goal_id is not None
                else None
            ),
            "owner_process_id": (
                str(record.owner_process_id)
                if record.owner_process_id is not None
                else None
            ),
            "space_id": record.space_id,
            "version": record.version,
            "status": record.status.value,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "updated_relative": format_relative_time(record.updated_at),
            "metadata": dict(record.metadata),
            "provenance": dict(record.provenance),
            "tags": list(record.tags),
            "mime_type": record.mime_type,
            "size_bytes": record.size_bytes,
            "size": format_bytes(record.size_bytes),
            "storage_key": record.storage_key,
            "knowledge_links": list(record.knowledge_links),
            "links": {key: list(values) for key, values in record.links.items()},
            "referenced_by_count": len(referenced_by),
            "referenced_by": referenced_by,
            "lineage_id": record.lineage_id,
        }
        if include_content:
            raw = self.read_content(record.artifact_id)
            if raw is not None:
                try:
                    view["content"] = raw.decode("utf-8")
                    view["binary"] = False
                except UnicodeDecodeError:
                    view["content"] = raw.decode("latin-1")
                    view["binary"] = True
        return view

    def _serialize_record(self, record: ArtifactRecord) -> dict[str, Any]:
        return {
            "artifact_id": str(record.artifact_id),
            "name": record.name,
            "artifact_type": record.artifact_type,
            "owner_goal_id": (
                str(record.owner_goal_id)
                if record.owner_goal_id is not None
                else None
            ),
            "owner_process_id": (
                str(record.owner_process_id)
                if record.owner_process_id is not None
                else None
            ),
            "space_id": record.space_id,
            "version": record.version,
            "status": record.status.value,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "metadata": record.metadata,
            "provenance": record.provenance,
            "tags": record.tags,
            "mime_type": record.mime_type,
            "size_bytes": record.size_bytes,
            "storage_key": record.storage_key,
            "knowledge_links": record.knowledge_links,
            "links": record.links,
        }

    def _deserialize_record(self, raw: dict[str, Any]) -> ArtifactRecord:
        goal_raw = raw.get("owner_goal_id")
        process_raw = raw.get("owner_process_id")
        return ArtifactRecord(
            artifact_id=ArtifactID.from_string(str(raw["artifact_id"])),
            name=str(raw["name"]),
            artifact_type=str(raw["artifact_type"]),
            owner_goal_id=(
                GoalID.from_string(str(goal_raw))
                if goal_raw is not None
                else None
            ),
            owner_process_id=(
                ProcessID.from_string(str(process_raw))
                if process_raw is not None
                else None
            ),
            space_id=str(raw.get("space_id", DEFAULT_SPACE_ID)),
            version=int(raw.get("version", 1)),
            status=ArtifactStatus(str(raw.get("status", ArtifactStatus.ACTIVE.value))),
            created_at=datetime.fromisoformat(str(raw["created_at"])),
            updated_at=datetime.fromisoformat(str(raw["updated_at"])),
            metadata=dict(raw.get("metadata", {})),
            provenance=dict(raw.get("provenance", {})),
            tags=list(raw.get("tags", [])),
            mime_type=raw.get("mime_type"),
            size_bytes=int(raw.get("size_bytes", 0)),
            storage_key=str(raw.get("storage_key", "")),
            knowledge_links=list(raw.get("knowledge_links", [])),
            links={
                key: list(values)
                for key, values in dict(raw.get("links", {})).items()
            },
        )

    def _goal_for_process(self, process_id: ProcessID | None) -> GoalID | None:
        if process_id is None or self._ctx is None:
            return None
        return self._ctx.goal_registry.goal_for_process(process_id)

    def _space_for_process(self, process_id: ProcessID | None) -> str:
        if process_id is None or self._ctx is None:
            return DEFAULT_SPACE_ID
        goal_id = self._ctx.goal_registry.goal_for_process(process_id)
        if goal_id is None:
            return DEFAULT_SPACE_ID
        record = self._ctx.goal_registry.get(goal_id)
        if record is None:
            return DEFAULT_SPACE_ID
        return record.space_id

    def _plugin_for_process(self, process_id: ProcessID) -> str | None:
        if self._ctx is None or not self._ctx.process_table.exists(process_id):
            return None
        return self._ctx.process_table.get(process_id).definition.name


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w.\- ]+", "_", name.strip()) or "artifact"
    return cleaned.replace(" ", "_")


def _guess_mime_type(name: str) -> str | None:
    guessed, _ = mimetypes.guess_type(name)
    return guessed


def create_artifact_service(event_bus: EventBus) -> ArtifactService:
    return ArtifactService(event_bus=event_bus)
