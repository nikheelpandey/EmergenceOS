"""Unit tests for OS kernel tools."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from emergence.cognitive.goal_registry import GoalKind
from emergence.core.event import Event, EventType
from emergence.core.ids import GoalID, ProcessID
from emergence.core.process_definition import ProcessDefinition
from emergence.core.budget_tracker import BudgetTracker
from emergence.events.event_bus import EventBus
from emergence.executor.tool_executor import ToolExecutor, ToolRegistry, capability_for_tool
from emergence.executor.tool_model import ToolRequest
from emergence.kernel.boot_context import bind_tools_kernel, create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.memory.memory_manager import MemoryManager
from emergence.memory.memory_store import MemoryStore
from emergence.security.capabilities import (
    CAPABILITY_BY_NAME,
    FILESYSTEM_READ,
    FILESYSTEM_WRITE,
    MEMORY_READ,
    PROCESS_CREATE,
    PROCESS_INSPECT,
    STATE_READ,
    TOOL_BROWSER,
    TOOL_SHELL,
)
from emergence.security.capability_manager import CapabilityManager
from emergence.security.security_manager import SecurityManager
from emergence.tools.registry_setup import register_kernel_tools
from emergence.tools.vfs import VirtualFilesystem
from tests.helpers import build_test_process_context


@pytest.fixture
def vfs_tmp(tmp_path):
    return VirtualFilesystem(root=tmp_path / "vfs")


class TestCapabilityForTool:
    def test_maps_os_tools(self):
        assert capability_for_tool("fs.read") == FILESYSTEM_READ
        assert capability_for_tool("fs.write") == FILESYSTEM_WRITE
        assert capability_for_tool("http.fetch") == TOOL_BROWSER
        assert capability_for_tool("shell.exec") == TOOL_SHELL
        assert capability_for_tool("knowledge.search") == MEMORY_READ
        assert capability_for_tool("event.search") == PROCESS_INSPECT
        assert capability_for_tool("state.query") == STATE_READ
        assert capability_for_tool("process.spawn") == PROCESS_CREATE
        assert capability_for_tool("schedule.at") == PROCESS_CREATE


class TestVirtualFilesystem:
    def test_write_read_list_stat_delete(self, vfs_tmp):
        vfs_tmp.write("work", "notes/todo.txt", "finish tools")
        assert vfs_tmp.read("work", "notes/todo.txt")["content"] == "finish tools"
        assert vfs_tmp.list("work", "notes")["entries"][0]["name"] == "todo.txt"
        assert vfs_tmp.stat("work", "notes/todo.txt")["is_dir"] is False
        vfs_tmp.delete("work", "notes/todo.txt")
        with pytest.raises(FileNotFoundError):
            vfs_tmp.read("work", "notes/todo.txt")

    def test_rejects_traversal(self, vfs_tmp):
        with pytest.raises(ValueError):
            vfs_tmp.read("work", "../secrets")


class TestFsTools:
    def test_fs_tools_via_executor(self, vfs_tmp):
        bus = EventBus()
        memory = MemoryManager(MemoryStore(), bus)
        registry = ToolRegistry()
        register_kernel_tools(registry, memory=memory, vfs=vfs_tmp)
        capabilities = CapabilityManager()
        security = SecurityManager(capabilities)
        executor = ToolExecutor(registry, bus, security, BudgetTracker())
        pid = ProcessID.new()
        for cap in ("filesystem.read", "filesystem.write", "tool.python"):
            capabilities.grant(str(pid), CAPABILITY_BY_NAME[cap])

        write = executor.execute(
            ToolRequest(tool_name="fs.write", arguments={
                "path": "report.md",
                "content": "# hello",
                "space_id": "test",
            }),
            pid,
        )
        assert write.success

        read = executor.execute(
            ToolRequest(tool_name="fs.read", arguments={
                "path": "report.md",
                "space_id": "test",
            }),
            pid,
        )
        assert read.success
        assert read.result == "# hello"


class TestStateAndEventTools:
    def test_state_query_and_event_search(self):
        ctx = create_kernel_context()
        ctx.state.set("pipeline:status", "running")
        ctx.event_bus.publish(
            Event(
                event_type=EventType.GOAL_CREATED,
                payload={"description": "search me"},
            )
        )

        registry = ctx.tools._registry  # noqa: SLF001
        pid = ProcessID.new()
        result_state = registry.invoke(
            "state.query",
            {"prefix": "pipeline:"},
            pid,
        )
        assert result_state["count"] == 1
        assert result_state["entries"][0]["key"] == "pipeline:status"

        result_events = registry.invoke(
            "event.search",
            {"query": "search", "limit": 5},
            pid,
        )
        assert result_events["count"] >= 1


class TestHttpFetch:
    def test_http_fetch_allowlist_blocks(self, monkeypatch):
        monkeypatch.setenv("EMERGENCE_HTTP_ALLOWLIST", "localhost")
        ctx = create_kernel_context()
        definition = ProcessDefinition(
            name="fetcher",
            implementation="x:y",
            required_permissions=frozenset({"tool.browser", "tool.python"}),
        )
        context = build_test_process_context(definition)
        for cap in ("tool.browser", "tool.python"):
            context.tools._security._capabilities.grant(  # noqa: SLF001
                str(context.process_id),
                CAPABILITY_BY_NAME[cap],
            )

        result = context.tools.invoke(
            "http.fetch",
            {"url": "https://example.com"},
        )
        assert not result.success
        assert "allowlist" in (result.error or "").lower()


class TestShellExec:
    def test_shell_exec_runs_command(self):
        ctx = create_kernel_context()
        definition = ProcessDefinition(
            name="shell_user",
            implementation="x:y",
            required_permissions=frozenset({"tool.shell", "tool.python"}),
        )
        context = build_test_process_context(definition)
        for cap in ("tool.shell", "tool.python"):
            context.tools._security._capabilities.grant(  # noqa: SLF001
                str(context.process_id),
                CAPABILITY_BY_NAME[cap],
            )
        result = context.tools.invoke("shell.exec", {"command": "echo ok"})
        assert result.success
        assert "ok" in result.result["stdout"]


class TestScheduleAt:
    def test_schedule_at_registers_entry(self):
        ctx = create_kernel_context()
        kernel = Kernel(ctx=ctx, executor=ctx.executor, lifecycle=LifecycleManager())
        bind_tools_kernel(kernel)

        goal_id = GoalID.new()
        ctx.goal_registry.register(goal_id, "scheduled work", kind=GoalKind.ONE_SHOT)

        class SchedulerUser:
            def run(self, context):
                fire_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
                return context.tools.invoke(
                    "schedule.at",
                    {
                        "fire_at": fire_at,
                        "process": "hello_world",
                        "description": "later",
                    },
                )

        ctx.executor.register_runner("scheduler_proc", SchedulerUser())
        definition = ProcessDefinition(
            name="scheduler_proc",
            implementation="scheduler_proc",
            required_permissions=frozenset({
                "process.create",
                "tool.python",
            }),
        )
        ctx.registry.register(definition)
        process = kernel.spawn(definition, goal_id=goal_id)
        kernel.run_next()
        assert process.state.value == "completed"
        pending = ctx.schedule_manager.pending_for_goal(goal_id)
        assert len(pending) == 1
        assert pending[0].process_definition_name == "hello_world"
