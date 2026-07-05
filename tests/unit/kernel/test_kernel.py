"""
Tests for emergence.kernel.kernel.Kernel.
"""

from __future__ import annotations

import pytest

from emergence.core.event import Event, EventType
from emergence.core.process_context import ProcessContext
from emergence.core.process_definition import ProcessDefinition
from emergence.core.state import ProcessState
from emergence.executor.executor import Executor
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.security.capabilities import DEFAULT_PROCESS_CAPABILITIES


class FakeRunner:
    def __init__(self, *, should_fail: bool = False):
        self.calls: list[ProcessContext] = []
        self._should_fail = should_fail

    def run(self, context: ProcessContext):
        self.calls.append(context)
        if self._should_fail:
            raise RuntimeError("runner exploded")


class EventCollector:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def handler(self, event: Event) -> None:
        self.events.append(event)


@pytest.fixture
def process_definition() -> ProcessDefinition:
    return ProcessDefinition(
        name="test",
        implementation="fake",
        version="1.0.0",
    )


@pytest.fixture
def kernel_setup(process_definition: ProcessDefinition):
    ctx = create_kernel_context()
    executor = Executor()
    lifecycle = LifecycleManager()
    runner = FakeRunner()

    executor.register_runner("fake", runner)
    ctx.registry.register(process_definition)

    kernel = Kernel(
        ctx=ctx,
        executor=executor,
        lifecycle=lifecycle,
    )

    return kernel, ctx, runner


class TestKernelSpawn:
    def test_spawn_registers_and_schedules_process(
        self,
        kernel_setup,
        process_definition: ProcessDefinition,
    ):
        kernel, _, _ = kernel_setup

        process = kernel.spawn(process_definition)

        assert kernel.process_count() == 1
        assert kernel.has_work() is True
        assert process.state == ProcessState.READY

    def test_spawn_creates_mailbox_and_grants_capabilities(
        self,
        kernel_setup,
        process_definition: ProcessDefinition,
    ):
        kernel, ctx, _ = kernel_setup

        process = kernel.spawn(process_definition)
        pid = str(process.process_id)

        assert ctx.mailboxes.exists(pid) is True
        assert ctx.capabilities.capabilities(pid) == DEFAULT_PROCESS_CAPABILITIES

    def test_spawn_publishes_lifecycle_events(
        self,
        kernel_setup,
        process_definition: ProcessDefinition,
    ):
        kernel, ctx, _ = kernel_setup
        collector = EventCollector()
        ctx.event_bus.subscribe(EventType.PROCESS_CREATED, collector.handler)
        ctx.event_bus.subscribe(EventType.PROCESS_READY, collector.handler)

        process = kernel.spawn(process_definition)

        assert [event.event_type for event in collector.events] == [
            EventType.PROCESS_CREATED,
            EventType.PROCESS_READY,
        ]
        assert all(
            event.source_process == process.process_id
            for event in collector.events
        )
        assert collector.events[0].correlation_id is not None
        assert collector.events[0].correlation_id == collector.events[1].correlation_id
        assert collector.events[0].causation_id is None
        assert collector.events[1].causation_id == collector.events[0].event_id

    def test_child_spawn_carries_parent_causation_id(
        self,
        kernel_setup,
        process_definition: ProcessDefinition,
    ):
        kernel, ctx, _ = kernel_setup
        collector = EventCollector()
        ctx.event_bus.subscribe(EventType.PROCESS_CREATED, collector.handler)

        parent = kernel.spawn(process_definition)
        parent_created = collector.events[0]

        child_def = ProcessDefinition(
            name="child",
            implementation="fake",
            version="1.0.0",
        )
        ctx.registry.register(child_def)

        kernel.spawn(
            child_def,
            parent_process_id=parent.process_id,
            causation_id=parent_created.event_id,
            correlation_id=parent_created.correlation_id,
        )

        child_created = collector.events[1]

        assert child_created.causation_id == parent_created.event_id
        assert child_created.correlation_id == parent_created.correlation_id


class TestKernelRunNext:
    def test_run_next_executes_and_completes_process(
        self,
        kernel_setup,
        process_definition: ProcessDefinition,
    ):
        kernel, _, runner = kernel_setup

        process = kernel.spawn(process_definition)
        result = kernel.run_next()

        assert result is process
        assert len(runner.calls) == 1
        assert runner.calls[0].process_id == process.process_id
        assert runner.calls[0].definition == process_definition
        assert process.state == ProcessState.COMPLETED
        assert kernel.has_work() is False

    def test_run_next_returns_none_when_scheduler_empty(
        self,
        kernel_setup,
    ):
        kernel, _, _ = kernel_setup

        assert kernel.run_next() is None

    def test_runner_exception_sets_failed_and_emits_event(
        self,
        process_definition: ProcessDefinition,
    ):
        ctx = create_kernel_context()
        executor = Executor()
        lifecycle = LifecycleManager()
        runner = FakeRunner(should_fail=True)
        collector = EventCollector()

        executor.register_runner("fake", runner)
        ctx.registry.register(process_definition)
        ctx.event_bus.subscribe(EventType.PROCESS_FAILED, collector.handler)

        kernel = Kernel(
            ctx=ctx,
            executor=executor,
            lifecycle=lifecycle,
        )

        process = kernel.spawn(process_definition)
        kernel.run_next()

        assert process.state == ProcessState.FAILED
        assert process.failure_reason == "runner exploded"
        assert len(collector.events) == 1
        assert collector.events[0].event_type == EventType.PROCESS_FAILED
        assert collector.events[0].payload["error"] == "runner exploded"

    def test_terminal_state_cleans_up_mailbox_and_capabilities(
        self,
        kernel_setup,
        process_definition: ProcessDefinition,
    ):
        kernel, ctx, _ = kernel_setup

        process = kernel.spawn(process_definition)
        pid = str(process.process_id)

        kernel.run_next()

        assert ctx.mailboxes.exists(pid) is False
        assert ctx.capabilities.capabilities(pid) == set()

    def test_invalid_transition_raises_value_error(
        self,
        kernel_setup,
        process_definition: ProcessDefinition,
    ):
        kernel, _, _ = kernel_setup

        process = kernel.spawn(process_definition)
        process.state = ProcessState.COMPLETED

        with pytest.raises(ValueError):
            kernel.run_next()
