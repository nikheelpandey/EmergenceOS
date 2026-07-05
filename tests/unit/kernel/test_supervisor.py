"""Tests for emergence.kernel.supervisor — M8."""

from __future__ import annotations

from emergence.core.process_context import ProcessContext
from emergence.core.process_definition import ProcessDefinition
from emergence.core.state import ProcessState
from emergence.executor.executor import Executor
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.kernel.supervisor import RecoveryAction, Supervisor


class TestSupervisor:
    def test_flaky_process_succeeds_on_retry(self):
        ctx = create_kernel_context()
        executor = Executor()
        attempts = {"count": 0}

        class FlakyRunner:
            def run(self, context: ProcessContext):
                attempts["count"] += 1
                if attempts["count"] < 3:
                    raise RuntimeError("transient failure")
                return "ok"

        definition = ProcessDefinition(
            name="flaky",
            implementation="flaky",
            version="1.0.0",
        )
        executor.register_runner("flaky", FlakyRunner())
        ctx.registry.register(definition)

        kernel = Kernel(ctx=ctx, executor=executor, lifecycle=LifecycleManager())
        supervisor = Supervisor(
            kernel=kernel,
            checkpoints=ctx.checkpoints,
            event_store=ctx.event_store,
        )

        process = kernel.spawn(definition)

        for _ in range(5):
            if process.state == ProcessState.COMPLETED:
                break
            kernel.run_next()

        assert attempts["count"] >= 3
        assert any(
            d.action == RecoveryAction.RETRY
            for d in supervisor.decisions
        )
