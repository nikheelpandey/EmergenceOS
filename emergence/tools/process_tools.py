from __future__ import annotations

from datetime import datetime
from typing import Any

from emergence.core.ids import GoalID, ProcessID
from emergence.tools.services import ToolServices


def create_process_spawn_handler(services: ToolServices):
    def handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        kernel = services.kernel
        if services.registry is None:
            raise RuntimeError("process registry not available")

        name = str(args.get("process", args.get("name", ""))).strip()
        if not name:
            raise ValueError("process name required")

        priority = int(args.get("priority", 0))
        goal_id_raw = args.get("goal_id")
        goal_id = None
        if goal_id_raw:
            goal_id = GoalID.from_string(str(goal_id_raw))
        elif services.goal_registry is not None:
            goal_id = services.goal_registry.goal_for_process(process_id)

        definition = services.registry.get(name)
        spawned = kernel.spawn(
            definition,
            goal_id=goal_id,
            parent_process_id=process_id,
            priority=priority,
        )
        return {
            "process_id": str(spawned.process_id),
            "name": spawned.definition.name,
            "state": spawned.state.value,
        }

    return handler


def create_process_status_handler(services: ToolServices):
    def handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        if services.process_table is None:
            raise RuntimeError("process table not available")

        target_raw = args.get("process_id", str(process_id))
        target = ProcessID.from_string(str(target_raw))
        if not services.process_table.exists(target):
            raise KeyError(f"process not found: {target_raw}")

        process = services.process_table.get(target)
        usage = None
        if services.budgets is not None:
            usage = services.budgets.usage(target)

        return {
            "process_id": str(process.process_id),
            "name": process.definition.name,
            "state": process.state.value,
            "age_seconds": process.age_seconds,
            "parent_id": (
                str(process.parent_process_id)
                if process.parent_process_id is not None
                else None
            ),
            "budget": (
                {
                    "tokens": usage.tokens,
                    "tool_invocations": usage.tool_invocations,
                    "execution_seconds": usage.execution_seconds,
                }
                if usage is not None
                else None
            ),
        }

    return handler


def create_process_find_handler(services: ToolServices):
    def handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        if services.process_table is None:
            raise RuntimeError("process table not available")

        name = args.get("name")
        state = args.get("state")
        goal_id_raw = args.get("goal_id")
        limit = int(args.get("limit", 50))

        goal_process_ids: set[str] | None = None
        if goal_id_raw and services.goal_registry is not None:
            goal_id = GoalID.from_string(str(goal_id_raw))
            record = services.goal_registry.get(goal_id)
            if record is not None:
                goal_process_ids = {str(pid) for pid in record.all_process_ids}

        results: list[dict[str, Any]] = []
        for process in services.process_table.all():
            if name and process.definition.name != name:
                continue
            if state and process.state.value != state:
                continue
            if goal_process_ids is not None:
                if str(process.process_id) not in goal_process_ids:
                    continue
            results.append(
                {
                    "process_id": str(process.process_id),
                    "name": process.definition.name,
                    "state": process.state.value,
                    "age_seconds": process.age_seconds,
                }
            )
            if len(results) >= limit:
                break

        return {"processes": results, "count": len(results)}

    return handler


def create_schedule_at_handler(services: ToolServices):
    def handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        if services.schedule_manager is None:
            raise RuntimeError("schedule manager not available")
        if services.goal_registry is None:
            raise RuntimeError("goal registry not available")

        fire_at_raw = str(args.get("fire_at", "")).strip()
        process_name = str(
            args.get("process", args.get("process_definition_name", ""))
        ).strip()
        if not fire_at_raw:
            raise ValueError("fire_at required")
        if not process_name:
            raise ValueError("process name required")

        goal_id = services.goal_registry.goal_for_process(process_id)
        if goal_id is None:
            goal_id_raw = args.get("goal_id")
            if not goal_id_raw:
                raise ValueError("goal_id required when caller has no goal")
            goal_id = GoalID.from_string(str(goal_id_raw))

        fire_at = datetime.fromisoformat(fire_at_raw)
        entry = services.schedule_manager.register(
            goal_id,
            process_name,
            fire_at,
            description=str(args.get("description", "")),
        )
        return {
            "schedule_id": entry.schedule_id,
            "goal_id": str(entry.goal_id),
            "process": entry.process_definition_name,
            "fire_at": entry.fire_at.isoformat(),
        }

    return handler
