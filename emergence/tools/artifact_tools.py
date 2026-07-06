from __future__ import annotations

from typing import Any

from emergence.core.ids import ArtifactID, GoalID, ProcessID
from emergence.tools.services import ToolServices


def create_artifact_handlers(services: ToolServices) -> dict[str, Any]:
    def _service():
        if services.artifact_service is None:
            raise RuntimeError("artifact service not available")
        return services.artifact_service

    def create_handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        name = str(args.get("name", "")).strip()
        artifact_type = str(args.get("type", args.get("artifact_type", ""))).strip()
        if not name:
            raise ValueError("name is required")
        if not artifact_type:
            raise ValueError("type is required")
        if "content" not in args:
            raise ValueError("content is required")

        goal_raw = args.get("goal_id")
        goal_id = GoalID.from_string(str(goal_raw)) if goal_raw else None
        based_on = args.get("based_on")

        record = _service().create(
            name=name,
            artifact_type=artifact_type,
            content=args["content"],
            owner_process_id=process_id,
            owner_goal_id=goal_id,
            space_id=args.get("space_id") or services.space_for_process(process_id),
            metadata=args.get("metadata"),
            provenance=args.get("provenance"),
            tags=args.get("tags"),
            mime_type=args.get("mime_type"),
            based_on=based_on,
            knowledge_links=args.get("knowledge_links"),
        )
        return _service()._to_view(record)  # noqa: SLF001

    def read_handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        artifact_id = str(args.get("artifact_id", "")).strip()
        if not artifact_id:
            raise ValueError("artifact_id is required")

        record = _service().get(
            artifact_id,
            version=int(args["version"]) if args.get("version") is not None else None,
        )
        if record is None:
            raise KeyError(f"artifact not found: {artifact_id}")
        return _service()._to_view(record, include_content=True)  # noqa: SLF001

    def update_handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        artifact_id = str(args.get("artifact_id", "")).strip()
        if not artifact_id:
            raise ValueError("artifact_id is required")
        if "content" not in args:
            raise ValueError("content is required")

        record = _service().update(
            artifact_id,
            content=args["content"],
            name=args.get("name"),
            metadata=args.get("metadata"),
            tags=args.get("tags"),
            owner_process_id=process_id,
        )
        return _service()._to_view(record)  # noqa: SLF001

    def delete_handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        artifact_id = str(args.get("artifact_id", "")).strip()
        if not artifact_id:
            raise ValueError("artifact_id is required")

        record = _service().delete(artifact_id)
        return _service()._to_view(record)  # noqa: SLF001

    def search_handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        goal_raw = args.get("goal_id")
        goal_id = GoalID.from_string(str(goal_raw)) if goal_raw else None
        artifact_type = args.get("type", args.get("artifact_type"))
        results = _service().search(
            query=args.get("query"),
            artifact_type=str(artifact_type) if artifact_type else None,
            goal_id=goal_id,
            space_id=args.get("space_id") or services.space_for_process(process_id),
            tags=args.get("tags"),
            latest_only=bool(args.get("latest_only", True)),
            limit=int(args.get("limit", 50)),
            include_content=bool(args.get("include_content", False)),
        )
        return {"results": results, "count": len(results)}

    def version_handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        artifact_id = str(args.get("artifact_id", "")).strip()
        if not artifact_id:
            raise ValueError("artifact_id is required")
        versions = _service().versions(artifact_id)
        return {"artifact_id": artifact_id, "versions": versions, "count": len(versions)}

    def watch_handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        return _service().register_watch(
            process_id,
            artifact_id=args.get("artifact_id"),
            artifact_type=args.get("type", args.get("artifact_type")),
            tags=args.get("tags"),
        )

    def link_handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        artifact_id = str(args.get("artifact_id", "")).strip()
        target_id = str(args.get("target_id", "")).strip()
        if not artifact_id:
            raise ValueError("artifact_id is required")
        if not target_id:
            raise ValueError("target_id is required")

        record = _service().link(
            artifact_id,
            target_id,
            link_type=str(args.get("link_type", "related")),
        )
        return _service()._to_view(record)  # noqa: SLF001

    def export_handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        artifact_id = str(args.get("artifact_id", "")).strip()
        if not artifact_id:
            raise ValueError("artifact_id is required")
        return _service().export(
            artifact_id,
            version=int(args["version"]) if args.get("version") is not None else None,
        )

    return {
        "artifact.create": create_handler,
        "artifact.read": read_handler,
        "artifact.update": update_handler,
        "artifact.delete": delete_handler,
        "artifact.search": search_handler,
        "artifact.version": version_handler,
        "artifact.watch": watch_handler,
        "artifact.link": link_handler,
        "artifact.export": export_handler,
    }
