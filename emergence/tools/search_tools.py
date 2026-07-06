from __future__ import annotations

import fnmatch
import json
from typing import Any

from emergence.core.ids import GoalID, ProcessID
from emergence.events.narrative import narrate_event
from emergence.memory.knowledge_index import ArtifactType
from emergence.tools.services import ToolServices


def create_knowledge_search_handler(services: ToolServices):
    def handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        if services.knowledge_index is None:
            raise RuntimeError("knowledge index not available")

        query = str(args.get("query", "")).strip().lower()
        top_k = int(args.get("top_k", 10))
        goal_id_raw = args.get("goal_id")
        artifact_type_raw = args.get("artifact_type")
        space_id = args.get("space_id") or services.space_for_process(process_id)

        parsed_goal = GoalID.from_string(str(goal_id_raw)) if goal_id_raw else None
        parsed_type = (
            ArtifactType(str(artifact_type_raw)) if artifact_type_raw else None
        )

        artifacts = services.knowledge_index.query(
            goal_id=parsed_goal,
            artifact_type=parsed_type,
            space_id=space_id,
            include_content=True,
        )

        if query:
            scored: list[tuple[int, dict[str, Any]]] = []
            for item in artifacts:
                key = str(item.get("key", "")).lower()
                content = str(item.get("content") or "").lower()
                score = 0
                if query in key:
                    score += 3
                if query in content:
                    score += 2
                for token in query.split():
                    if token in key:
                        score += 1
                    if token in content:
                        score += 1
                if score > 0:
                    scored.append((score, item))
            scored.sort(key=lambda pair: pair[0], reverse=True)
            artifacts = [item for _, item in scored[:top_k]]
        else:
            artifacts = artifacts[:top_k]

        return {"results": artifacts, "count": len(artifacts)}

    return handler


def create_knowledge_get_handler(services: ToolServices):
    def handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        if services.knowledge_index is None:
            raise RuntimeError("knowledge index not available")

        artifact_id = str(args.get("artifact_id", "")).strip()
        if not artifact_id:
            raise ValueError("artifact_id required")

        artifact = services.knowledge_index.get(artifact_id)
        if artifact is None:
            raise KeyError(f"artifact not found: {artifact_id}")

        return services.knowledge_index._to_view(  # noqa: SLF001
            artifact,
            include_content=True,
        )

    return handler


def create_event_search_handler(services: ToolServices):
    def handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        if services.event_store is None:
            raise RuntimeError("event store not available")

        from emergence.core.event import EventType

        limit = int(args.get("limit", 50))
        query_text = str(args.get("query", "")).strip().lower()
        goal_id_raw = args.get("goal_id")
        correlation_id_raw = args.get("correlation_id")
        event_type_raw = args.get("event_type")
        source_process_raw = args.get("source_process")

        event_type = None
        if event_type_raw:
            event_type = EventType(str(event_type_raw))

        source_process = None
        if source_process_raw:
            source_process = ProcessID.from_string(str(source_process_raw))

        correlation_id = None
        if correlation_id_raw:
            from uuid import UUID

            correlation_id = UUID(str(correlation_id_raw))

        events = services.event_store.query(
            event_type=event_type,
            source_process=source_process,
            correlation_id=correlation_id,
        )

        if goal_id_raw and services.goal_registry is not None:
            goal_id = GoalID.from_string(str(goal_id_raw))
            record = services.goal_registry.get(goal_id)
            process_ids = (
                {str(pid) for pid in record.all_process_ids}
                if record is not None
                else set()
            )
            events = [
                event
                for event in events
                if event.source_process is not None
                and str(event.source_process) in process_ids
            ]

        results: list[dict[str, Any]] = []
        for event in reversed(events):
            plugin = None
            if event.source_process and services.process_table:
                if services.process_table.exists(event.source_process):
                    plugin = (
                        services.process_table.get(event.source_process)
                        .definition.name
                    )
            narrative = narrate_event(event, plugin=plugin)
            payload_text = json.dumps(event.payload, default=str).lower()
            if query_text and query_text not in (narrative or "").lower():
                if query_text not in event.event_type.value.lower():
                    if query_text not in payload_text:
                        continue
            results.append(
                {
                    "event_id": str(event.event_id),
                    "event_type": event.event_type.value,
                    "timestamp": event.timestamp.isoformat(),
                    "narrative": narrative,
                    "source_process": (
                        str(event.source_process)
                        if event.source_process is not None
                        else None
                    ),
                    "correlation_id": (
                        str(event.correlation_id)
                        if event.correlation_id is not None
                        else None
                    ),
                }
            )
            if len(results) >= limit:
                break

        return {"events": results, "count": len(results)}

    return handler


def create_state_query_handler(services: ToolServices):
    def handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        if services.state is None:
            raise RuntimeError("state store not available")

        prefix = str(args.get("prefix", ""))
        pattern = str(args.get("pattern", "*"))
        limit = int(args.get("limit", 100))

        matches: list[dict[str, Any]] = []
        for key in services.state.keys():
            if prefix and not key.startswith(prefix):
                continue
            if not fnmatch.fnmatch(key, pattern):
                continue
            matches.append({"key": key, "value": services.state.get(key)})
            if len(matches) >= limit:
                break

        return {"entries": matches, "count": len(matches)}

    return handler
