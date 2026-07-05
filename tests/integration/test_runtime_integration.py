"""
Integration tests for M2 runtime wiring.

Validates that processes execute through ProcessContext and can
interact with kernel services such as the StateStore.
"""

from __future__ import annotations

import pytest

from emergence.core.process_context import ProcessContext
from emergence.core.process_definition import ProcessDefinition
from emergence.core.state import ProcessState
from emergence.executor.executor import Executor
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager


class StateWriterRunner:
    def run(self, context: ProcessContext) -> str:
        context.state.set("greeting", f"hello:{context.definition.name}")
        return context.state.get("greeting")


@pytest.mark.integration
class TestRuntimeIntegration:
    def test_spawn_execute_reads_and_writes_state_via_context(self):
        ctx = create_kernel_context()
        executor = Executor()
        definition = ProcessDefinition(
            name="state_writer",
            implementation="state_writer",
            version="1.0.0",
        )

        executor.register_runner("state_writer", StateWriterRunner())
        ctx.registry.register(definition)

        kernel = Kernel(
            ctx=ctx,
            executor=executor,
            lifecycle=LifecycleManager(),
        )

        process = kernel.spawn(definition)
        kernel.run_next()

        assert process.state == ProcessState.COMPLETED
        assert ctx.state.get("greeting") == "hello:state_writer"

    def test_python_runner_receives_process_context(self):
        ctx = create_kernel_context()
        executor = Executor()
        captured: list[ProcessContext] = []

        class CaptureRunner:
            def run(self, context: ProcessContext):
                captured.append(context)
                context.state.set("seen", True)
                return "ok"

        definition = ProcessDefinition(
            name="capture",
            implementation="capture",
            version="1.0.0",
        )

        executor.register_runner("capture", CaptureRunner())
        ctx.registry.register(definition)

        kernel = Kernel(
            ctx=ctx,
            executor=executor,
            lifecycle=LifecycleManager(),
        )
        kernel.spawn(definition)
        kernel.run_next()

        assert len(captured) == 1
        assert isinstance(captured[0], ProcessContext)
        assert ctx.state.get("seen") is True
