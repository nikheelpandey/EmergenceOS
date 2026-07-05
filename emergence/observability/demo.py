"""
observability/demo.py

Build a demo kernel with processes in mixed lifecycle states.
"""

from __future__ import annotations

from emergence.core.process_context import ProcessContext
from emergence.core.process_definition import ProcessDefinition
from emergence.executor.executor import Executor
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager


class _FastRunner:
    def run(self, context: ProcessContext) -> str:
        context.state.set("last_completed", context.definition.name)
        return "ok"


class _PendingRunner:
    def run(self, context: ProcessContext) -> str:
        return "pending"


class _FailRunner:
    def run(self, context: ProcessContext) -> str:
        raise RuntimeError("demo failure")


def build_demo_kernel() -> Kernel:
    """
    Create a kernel with completed, failed, and queued processes.
    """

    ctx = create_kernel_context()
    executor = Executor()
    lifecycle = LifecycleManager()

    definitions = {
        "fast": ProcessDefinition(
            name="fast",
            implementation="fast",
            version="1.0.0",
        ),
        "pending": ProcessDefinition(
            name="pending",
            implementation="pending",
            version="1.0.0",
        ),
        "fail": ProcessDefinition(
            name="fail",
            implementation="fail",
            version="1.0.0",
        ),
    }

    executor.register_runner("fast", _FastRunner())
    executor.register_runner("pending", _PendingRunner())
    executor.register_runner("fail", _FailRunner())

    for definition in definitions.values():
        ctx.registry.register(definition)

    kernel = Kernel(ctx=ctx, executor=executor, lifecycle=lifecycle)

    kernel.spawn(definitions["fast"])
    kernel.spawn(definitions["fail"])
    kernel.spawn(definitions["pending"])

    kernel.run_next()
    kernel.run_next()

    return kernel
