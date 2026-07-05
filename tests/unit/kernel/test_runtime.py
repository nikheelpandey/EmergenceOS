"""Tests for persistent kernel runtime."""

from __future__ import annotations

import threading
import time

import pytest

from emergence.core.event import EventType
from emergence.core.process_definition import ProcessDefinition
from emergence.executor.executor import Executor
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.kernel.runtime import build_runtime


class WaitingRunner:
    """Runner that yields to WAITING like a long-lived service."""

    def run(self, context):
        from emergence.core.process_waiting import ProcessWaiting
        from emergence.core.wait_conditions import TimerWaitCondition
        from datetime import UTC, datetime, timedelta

        raise ProcessWaiting(
            TimerWaitCondition(datetime.now(UTC) + timedelta(hours=1))
        )


class TestRunForever:
    def test_run_forever_stays_alive_while_processes_waiting(self):
        ctx = create_kernel_context(executor=Executor())
        runner = WaitingRunner()
        ctx.executor.register_runner("waiter", runner)
        definition = ProcessDefinition(
            name="waiter",
            implementation="waiter",
        )
        ctx.registry.register(definition)

        kernel = Kernel(
            ctx=ctx,
            executor=ctx.executor,
            lifecycle=LifecycleManager(),
        )
        kernel.spawn(definition)
        kernel.run_next()

        assert kernel.has_work() is False
        assert kernel.live_process_count() == 1

        # Batch run would exit here; run_forever keeps going
        stopped = threading.Event()

        def run():
            kernel.run_forever(poll_interval=0.01)
            stopped.set()

        thread = threading.Thread(target=run)
        thread.start()

        time.sleep(0.15)
        assert kernel.is_running is True
        assert not stopped.is_set()

        kernel.shutdown()
        thread.join(timeout=3)
        assert stopped.is_set()

    def test_shutdown_publishes_kernel_stopped(self):
        ctx = create_kernel_context(executor=Executor())
        kernel = Kernel(
            ctx=ctx,
            executor=ctx.executor,
            lifecycle=LifecycleManager(),
        )
        events = []
        ctx.event_bus.subscribe(
            EventType.KERNEL_STOPPED,
            lambda e: events.append(e),
        )

        kernel._running = True
        kernel.shutdown()
        kernel._publish_shutdown()

        assert len(events) == 1


class TestBuildRuntime:
    def test_spawns_platform_services(self):
        kernel = build_runtime()
        names = {
            p.definition.name
            for p in kernel.context.process_table.all()
        }
        assert "heartbeat" in names
        assert "event_collector" in names
        assert "job_worker" in names
        assert kernel.context.state.get("os:status") == "running"

        # Drain one round — services should enter WAITING, not exit
        for _ in range(5):
            if kernel.has_work():
                kernel.run_next()

        assert kernel.live_process_count() >= 1
