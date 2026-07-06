"""
Register kernel tools on a ToolRegistry.

Centralizes tool wiring so boot_context and tests share the same setup.
"""

from __future__ import annotations

from typing import Any

from emergence.core.ids import ProcessID
from emergence.executor.tool_executor import ToolRegistry
from emergence.memory.memory_category import MemoryCategory
from emergence.memory.memory_manager import MemoryManager
from emergence.tools.artifact_tools import create_artifact_handlers
from emergence.tools.fs_tools import create_fs_handlers
from emergence.tools.llm import LLMProvider, create_llm_chat_handler
from emergence.tools.network import create_http_fetch_handler
from emergence.tools.process_tools import (
    create_process_find_handler,
    create_process_spawn_handler,
    create_process_status_handler,
    create_schedule_at_handler,
)
from emergence.tools.search_tools import (
    create_event_search_handler,
    create_knowledge_get_handler,
    create_knowledge_search_handler,
    create_state_query_handler,
)
from emergence.tools.services import ToolServices
from emergence.tools.shell_tool import create_shell_exec_handler
from emergence.tools.vfs import VirtualFilesystem


def create_memory_search_handler(
    memory: MemoryManager,
) -> Any:
    """Return a ToolRegistry handler for ``memory.search``."""

    def handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        query = args.get("query", "")
        top_k = int(args.get("top_k", 5))
        categories = args.get("categories", ["episodic", "semantic"])

        parsed: list[MemoryCategory] = []
        for name in categories:
            try:
                parsed.append(MemoryCategory(name))
            except ValueError:
                continue

        if not parsed:
            parsed = [MemoryCategory.EPISODIC, MemoryCategory.SEMANTIC]

        results = memory.search(
            process_id,
            query,
            categories=parsed,
            top_k=top_k,
        )
        return {"results": results, "count": len(results)}

    return handler


def register_kernel_tools(
    registry: ToolRegistry,
    *,
    memory: MemoryManager,
    llm_provider: LLMProvider | None = None,
    services: ToolServices | None = None,
    vfs: VirtualFilesystem | None = None,
) -> ToolServices:
    """Register all built-in kernel tools and return shared services."""

    tool_services = services or ToolServices()
    vfs_instance = vfs or VirtualFilesystem()
    registry.services = tool_services  # type: ignore[attr-defined]

    registry.register(
        "echo",
        lambda args, process_id: args.get("message", ""),
    )
    registry.register(
        "llm.chat",
        create_llm_chat_handler(llm_provider),
    )
    registry.register(
        "memory.search",
        create_memory_search_handler(memory),
    )

    for name, handler in create_fs_handlers(tool_services, vfs_instance).items():
        registry.register(name, handler)

    registry.register("http.fetch", create_http_fetch_handler())
    registry.register("shell.exec", create_shell_exec_handler())

    registry.register(
        "knowledge.search",
        create_knowledge_search_handler(tool_services),
    )
    registry.register(
        "knowledge.get",
        create_knowledge_get_handler(tool_services),
    )

    for name, handler in create_artifact_handlers(tool_services).items():
        registry.register(name, handler)

    registry.register(
        "event.search",
        create_event_search_handler(tool_services),
    )
    registry.register(
        "state.query",
        create_state_query_handler(tool_services),
    )

    registry.register(
        "process.spawn",
        create_process_spawn_handler(tool_services),
    )
    registry.register(
        "process.status",
        create_process_status_handler(tool_services),
    )
    registry.register(
        "process.find",
        create_process_find_handler(tool_services),
    )
    registry.register(
        "schedule.at",
        create_schedule_at_handler(tool_services),
    )

    return tool_services
