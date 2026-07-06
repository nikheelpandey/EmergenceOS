"""Integration tests for OS kernel tools."""

from __future__ import annotations

import pytest

from emergence.core.process_definition import ProcessDefinition
from emergence.core.state import ProcessState
from emergence.kernel.boot_context import build_kernel
from emergence.memory.memory_category import MemoryCategory


@pytest.mark.integration
class TestOsToolsIntegration:
    def test_knowledge_search_finds_stored_finding(self):
        kernel = build_kernel(spawn=None, load_plugins=False)

        class ResearchStore:
            def run(self, context):
                context.memory.store(
                    "finding_alpha",
                    "Event-driven mailboxes coordinate autonomous agents",
                    category=MemoryCategory.EPISODIC,
                )
                return context.tools.invoke(
                    "knowledge.search",
                    {"query": "mailboxes", "top_k": 5},
                )

        ctx = kernel.context
        ctx.executor.register_runner("research_store", ResearchStore())
        definition = ProcessDefinition(
            name="research_store",
            implementation="research_store",
            required_permissions=frozenset({
                "memory.read",
                "memory.write",
                "tool.python",
            }),
        )
        ctx.registry.register(definition)
        process = kernel.spawn(definition)
        kernel.run_next()
        assert process.state == ProcessState.COMPLETED
        assert ctx.knowledge_index.query(include_content=True)

    def test_process_spawn_via_tool(self):
        kernel = build_kernel(spawn=None, load_plugins=True)

        class Spawner:
            def run(self, context):
                return context.tools.invoke(
                    "process.spawn",
                    {"process": "hello_world", "priority": 3},
                )

        ctx = kernel.context
        ctx.executor.register_runner("spawner", Spawner())
        definition = ProcessDefinition(
            name="spawner",
            implementation="spawner",
            required_permissions=frozenset({
                "process.create",
                "tool.python",
            }),
        )
        ctx.registry.register(definition)
        process = kernel.spawn(definition)
        kernel.run_next()
        assert process.state == ProcessState.COMPLETED
        assert len(ctx.process_table.all()) >= 2
