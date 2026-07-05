"""
Integration test simulating the EmergenceOS system model.

Exercises the full M3 + M4 pipeline:

    Coordinator ──request──▶ Researcher ──findings──▶ State
         ▲                        │
         └──response──────────────┘
                                  │
                                  ▼
                              Evaluator (depends on Researcher)
"""

from __future__ import annotations

import pytest

from emergence.core.budget import ResourceBudget
from emergence.core.event import EventType
from emergence.core.process_context import ProcessContext
from emergence.core.process_definition import ProcessDefinition
from emergence.core.state import ProcessState
from emergence.executor.executor import Executor
from emergence.executor.python_runner import PythonRunner
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.security.capabilities import STATE_READ, STATE_WRITE


@pytest.mark.integration
class TestSystemModelSimulation:
    def test_coordinator_researcher_evaluator_pipeline(self):
        ctx = create_kernel_context()
        executor = Executor()
        lifecycle = LifecycleManager()

        demo = "emergence.apps.system_model_demo"
        executor.register_runner(f"{demo}:run_researcher", PythonRunner())
        executor.register_runner(f"{demo}:run_coordinator", PythonRunner())
        executor.register_runner(f"{demo}:run_evaluator", PythonRunner())
        executor.register_runner(f"{demo}:run_restricted", PythonRunner())

        researcher_def = ProcessDefinition(
            name="researcher",
            implementation=f"{demo}:run_researcher",
            version="1.0.0",
            default_budget=ResourceBudget(max_execution_time_seconds=60),
        )
        coordinator_def = ProcessDefinition(
            name="coordinator",
            implementation=f"{demo}:run_coordinator",
            version="1.0.0",
            default_budget=ResourceBudget(max_execution_time_seconds=60),
        )
        evaluator_def = ProcessDefinition(
            name="evaluator",
            implementation=f"{demo}:run_evaluator",
            version="1.0.0",
            default_budget=ResourceBudget(max_execution_time_seconds=60),
        )
        restricted_def = ProcessDefinition(
            name="restricted",
            implementation=f"{demo}:run_restricted",
            version="1.0.0",
            required_permissions=frozenset({"state.read"}),
        )

        for definition in (
            researcher_def,
            coordinator_def,
            evaluator_def,
            restricted_def,
        ):
            ctx.registry.register(definition)

        kernel = Kernel(ctx=ctx, executor=executor, lifecycle=lifecycle)

        waiting_events: list = []
        ctx.event_bus.subscribe(
            EventType.PROCESS_WAITING,
            lambda e: waiting_events.append(e),
        )
        message_events: list = []
        ctx.event_bus.subscribe(
            EventType.MESSAGE_RECEIVED,
            lambda e: message_events.append(e),
        )

        researcher = kernel.spawn(researcher_def, priority=5)
        coordinator = kernel.spawn(coordinator_def, priority=10)
        evaluator = kernel.spawn(
            evaluator_def,
            priority=3,
            depends_on=(researcher.process_id,),
        )

        ctx.state.set("researcher_pid", str(researcher.process_id))

        # Phase 1: researcher waits, coordinator sends request
        kernel.run_next()  # coordinator (priority 10)
        assert coordinator.state == ProcessState.WAITING
        assert ctx.state.get("pipeline_status") == "request_sent"
        assert len(message_events) >= 1

        kernel.run_next()  # researcher processes request
        assert researcher.state == ProcessState.COMPLETED
        assert ctx.state.get("research_findings") is not None
        assert ctx.state.get("pipeline_status") == "research_complete"

        # Phase 2: coordinator wakes on response, evaluator runs (dep met)
        assert kernel.has_work() is True
        kernel.run_next()  # coordinator receives response
        assert coordinator.state == ProcessState.COMPLETED

        kernel.run_next()  # evaluator
        assert evaluator.state == ProcessState.COMPLETED
        assert ctx.state.get("evaluation") is not None
        assert ctx.state.get("pipeline_status") == "goal_completed"

        assert len(waiting_events) >= 1

    def test_restricted_process_denied_state_write(self):
        ctx = create_kernel_context()
        executor = Executor()

        demo = "emergence.apps.system_model_demo"
        executor.register_runner(f"{demo}:run_restricted", PythonRunner())

        restricted_def = ProcessDefinition(
            name="restricted",
            implementation=f"{demo}:run_restricted",
            version="1.0.0",
            required_permissions=frozenset({"state.read"}),
        )
        ctx.registry.register(restricted_def)

        kernel = Kernel(
            ctx=ctx,
            executor=executor,
            lifecycle=LifecycleManager(),
        )

        process = kernel.spawn(restricted_def)
        pid = str(process.process_id)

        ctx.capabilities.revoke(pid, STATE_WRITE)
        ctx.capabilities.grant(pid, STATE_READ)

        kernel.run_next()

        assert process.state == ProcessState.FAILED
        assert "state.write" in process.failure_reason

    def test_budget_timeout_fails_process(self):
        ctx = create_kernel_context()
        executor = Executor()

        definition = ProcessDefinition(
            name="slow",
            implementation="slow",
            version="1.0.0",
            default_budget=ResourceBudget(
                max_execution_time_seconds=1,
            ),
        )

        class SlowRunner:
            def run(self, context: ProcessContext):
                import time
                time.sleep(1.5)
                return "done"

        executor.register_runner("slow", SlowRunner())
        ctx.registry.register(definition)

        kernel = Kernel(
            ctx=ctx,
            executor=executor,
            lifecycle=LifecycleManager(),
        )

        process = kernel.spawn(definition)
        kernel.run_next()

        assert process.state == ProcessState.FAILED
        assert "budget" in process.failure_reason.lower()

    def test_higher_priority_runs_first(self):
        ctx = create_kernel_context()
        executor = Executor()
        order: list[str] = []

        class OrderRunner:
            def __init__(self, name: str):
                self._name = name

            def run(self, context: ProcessContext):
                order.append(self._name)

        low_def = ProcessDefinition(
            name="low",
            implementation="low",
            version="1.0.0",
        )
        high_def = ProcessDefinition(
            name="high",
            implementation="high",
            version="1.0.0",
        )

        executor.register_runner("low", OrderRunner("low"))
        executor.register_runner("high", OrderRunner("high"))
        ctx.registry.register(low_def)
        ctx.registry.register(high_def)

        kernel = Kernel(
            ctx=ctx,
            executor=executor,
            lifecycle=LifecycleManager(),
        )

        kernel.spawn(low_def, priority=1)
        kernel.spawn(high_def, priority=10)

        kernel.run_next()
        kernel.run_next()

        assert order == ["high", "low"]
