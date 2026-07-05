"""Tests for emergence.core.execution_spec — M10."""

from __future__ import annotations

import pytest

from emergence.core.event import EventType
from emergence.core.execution_spec import ExecutionSpec
from emergence.core.process_context import ProcessContext
from emergence.core.process_definition import ProcessDefinition
from emergence.executor.executor import Executor
from emergence.executor.python_runner import PythonRunner
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager


class TestExecutionSpec:
    def test_process_definition_derives_implementation(self):
        spec = ExecutionSpec(
            runner="python",
            target="emergence.apps.hello_world:run",
        )
        definition = ProcessDefinition(
            name="hw",
            execution_spec=spec,
            version="1.0.0",
        )
        assert definition.implementation == spec.target
        assert definition.runner_key == spec.target

    def test_tool_invocation_produces_event_chain(self):
        ctx = create_kernel_context()
        executor = Executor()

        class ToolUserRunner:
            def run(self, context: ProcessContext):
                result = context.tools.invoke(
                    "echo",
                    {"message": "tool-ok"},
                )
                return result.result

        spec = ExecutionSpec(
            runner="python",
            target="tool_user",
        )
        definition = ProcessDefinition(
            name="tool_user",
            execution_spec=spec,
            version="1.0.0",
            required_permissions=frozenset({"tool.python"}),
        )
        executor.register_runner("tool_user", ToolUserRunner())
        ctx.registry.register(definition)

        kernel = Kernel(
            ctx=ctx,
            executor=executor,
            lifecycle=LifecycleManager(),
        )
        events = []
        ctx.event_bus.subscribe(
            EventType.TOOL_COMPLETED,
            lambda e: events.append(e),
        )

        kernel.spawn(definition)
        kernel.run_next()

        assert len(events) == 1
        assert events[0].payload["result"] == "tool-ok"

    def test_empty_spec_raises(self):
        with pytest.raises(ValueError):
            ExecutionSpec(runner="", target="x")
