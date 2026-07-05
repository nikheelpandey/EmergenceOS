"""Integration tests for LLM tools and cognitive AI milestones M13-M18."""

from __future__ import annotations

from pathlib import Path

import pytest

from emergence.core.event import EventType
from emergence.core.state import GoalState, PlanState
from emergence.executor.executor import Executor
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.memory.memory_category import MemoryCategory
from emergence.security.capabilities import TOOL_LLM
from emergence.tools.llm import MockLLMProvider

PLUGINS_ROOT = Path(__file__).resolve().parents[2] / "plugins"


@pytest.fixture
def ai_kernel():
    """Kernel with mock LLM and all AI plugins loaded."""
    executor = Executor()
    ctx = create_kernel_context(
        executor=executor,
        llm_provider=MockLLMProvider(),
    )

    ctx.plugins.load_all()
    kernel = Kernel(
        ctx=ctx,
        executor=ctx.executor,
        lifecycle=LifecycleManager(),
    )
    return kernel


class TestLLMToolIntegration:
    def test_llm_chat_enforces_budget(self, ai_kernel):
        kernel = ai_kernel
        ctx = kernel.context

        from emergence.core.process_definition import ProcessDefinition

        tool_events = []
        ctx.event_bus.subscribe(
            EventType.TOOL_COMPLETED,
            lambda e: tool_events.append(e),
        )

        class LLMCaller:
            def run(self, context):
                return context.tools.invoke(
                    "llm.chat",
                    {"prompt": "Research event-driven systems"},
                )

        spec_def = ProcessDefinition(
            name="llm_caller",
            implementation="llm_caller",
            required_permissions=frozenset({"tool.llm"}),
        )
        ctx.executor.register_runner("llm_caller", LLMCaller())
        ctx.registry.register(spec_def)

        process = kernel.spawn(spec_def)
        kernel.run_next()

        assert process.state.value == "completed"
        assert len(tool_events) == 1
        assert tool_events[0].payload["tokens_used"] > 0

    def test_llm_requires_tool_llm_capability(self, ai_kernel):
        kernel = ai_kernel
        ctx = kernel.context

        from emergence.core.process_definition import ProcessDefinition

        class LLMCaller:
            def run(self, context):
                return context.tools.invoke("llm.chat", {"prompt": "hi"})

        spec_def = ProcessDefinition(
            name="no_llm",
            implementation="no_llm",
            required_permissions=frozenset({"tool.python"}),
        )
        ctx.executor.register_runner("no_llm", LLMCaller())
        ctx.registry.register(spec_def)

        process = kernel.spawn(spec_def)
        kernel.run_next()

        assert process.state.value == "failed"


class TestMemorySearchIntegration:
    def test_memory_search_tool(self, ai_kernel):
        kernel = ai_kernel
        ctx = kernel.context

        from emergence.core.process_definition import ProcessDefinition

        class Searcher:
            def run(self, context):
                context.memory.store(
                    "finding_1",
                    "Event-driven architecture uses observable mailboxes",
                    category=MemoryCategory.EPISODIC,
                )
                return context.tools.invoke(
                    "memory.search",
                    {"query": "event-driven mailboxes"},
                )

        spec_def = ProcessDefinition(
            name="searcher",
            implementation="searcher",
            required_permissions=frozenset({
                "tool.python",
                "memory.read",
                "memory.write",
            }),
        )
        ctx.executor.register_runner("searcher", Searcher())
        ctx.registry.register(spec_def)

        process = kernel.spawn(spec_def)
        kernel.run_next()
        assert process.state.value == "completed"


class TestPlannerIntegration:
    def test_create_plan_from_goal(self, ai_kernel):
        kernel = ai_kernel
        ctx = kernel.context
        ctx.state.set("research_topic", "EmergenceOS")

        goal, plan = kernel.create_plan_from_goal("Research EmergenceOS")
        assert goal.state == GoalState.IN_PROGRESS
        assert plan.state == PlanState.ACTIVE

        tasks = ctx.cognitive.tasks_for_plan(plan.plan_id)
        assert len(tasks) >= 2
        names = {t.name for t in tasks}
        assert "research" in names


class TestResearchAssistantIntegration:
    def test_research_assistant_end_to_end(self, ai_kernel):
        kernel = ai_kernel
        ctx = kernel.context

        ctx.state.set("research_topic", "EmergenceOS architecture")
        ctx.state.set("auto_approve", True)

        kernel.spawn(ctx.registry.get("research_assistant"), priority=10)
        kernel.run()

        assert ctx.state.get("pipeline_status") == "completed"
        assert ctx.state.get("research_report") is not None
        assert ctx.event_store.count() > 0


class TestHumanInTheLoop:
    def test_wait_for_approval_flow(self, ai_kernel):
        kernel = ai_kernel
        ctx = kernel.context

        from emergence.core.process_definition import ProcessDefinition

        approval_events = []
        ctx.event_bus.subscribe(
            EventType.USER_APPROVAL_REQUESTED,
            lambda e: approval_events.append(e),
        )

        class Approver:
            def run(self, context):
                rid = "test-approval-123"
                if not context.state.get(f"approval:{rid}"):
                    context.wait_for_approval(rid, message="Proceed?")
                return "approved"

        spec_def = ProcessDefinition(
            name="approver",
            implementation="approver",
            required_permissions=frozenset({"event.publish", "state.read"}),
        )
        ctx.executor.register_runner("approver", Approver())
        ctx.registry.register(spec_def)

        process = kernel.spawn(spec_def)
        kernel.run_next()
        assert process.state.value == "waiting"
        assert len(approval_events) == 1

        kernel.grant_user_approval("test-approval-123")
        kernel.run()

        assert process.state.value == "completed"
