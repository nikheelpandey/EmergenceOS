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
from emergence.tools.llm import LLMProvider, create_llm_chat_handler


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
) -> None:
    """Register all built-in kernel tools."""

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
