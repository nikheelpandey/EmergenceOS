"""
Tests for emergence.kernel.boot_context.
"""

from __future__ import annotations

from emergence.kernel.boot_context import build_kernel, create_kernel_context
from emergence.kernel.context import KernelContext
from emergence.kernel.kernel import Kernel


class TestCreateKernelContext:
    def test_returns_kernel_context(self):
        ctx = create_kernel_context()

        assert isinstance(ctx, KernelContext)

    def test_services_are_wired(self):
        ctx = create_kernel_context()

        assert ctx.event_bus is not None
        assert ctx.state is not None
        assert ctx.scheduler is not None
        assert ctx.registry is not None
        assert ctx.process_table is not None
        assert ctx.mailboxes is not None
        assert ctx.capabilities is not None


class TestBuildKernel:
    def test_returns_kernel_without_spawn(self):
        kernel = build_kernel(spawn=None)

        assert isinstance(kernel, Kernel)
        assert kernel.process_count() == 0
        assert kernel.has_work() is False

    def test_spawns_hello_world_by_default(self):
        kernel = build_kernel()

        assert kernel.process_count() == 1
        assert kernel.has_work() is True

    def test_run_completes_hello_world(self, capsys):
        kernel = build_kernel()

        kernel.run()

        assert kernel.has_work() is False
        assert kernel.process_count() == 1
        assert "Hello from plugin: hello_world" in capsys.readouterr().out
