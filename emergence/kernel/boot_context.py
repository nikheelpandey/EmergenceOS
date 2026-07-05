from __future__ import annotations

from pathlib import Path
from typing import Any

from emergence.checkpoint.checkpoint_manager import CheckpointManager
from emergence.cognitive.manager import CognitiveManager
from emergence.core.budget import ResourceBudget
from emergence.core.budget_tracker import BudgetTracker
from emergence.events.event_store import EventStore
from emergence.events.persisting_event_bus import PersistingEventBus
from emergence.executor.executor import Executor
from emergence.executor.tool_executor import ToolExecutor, ToolRegistry
from emergence.tools.registry_setup import register_kernel_tools
from emergence.kernel.context import KernelContext
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.kernel.mailbox_manager import MailboxManager
from emergence.kernel.process_table import ProcessTable
from emergence.kernel.registry import ProcessRegistry
from emergence.kernel.state_store import StateStore
from emergence.kernel.supervisor import Supervisor
from emergence.memory.memory_manager import MemoryManager
from emergence.memory.memory_store import MemoryStore
from emergence.observability.kernel import ObservabilityKernel
from emergence.plugins.manager import PluginManager
from emergence.scheduler.scheduler import Scheduler
from emergence.security.capability_manager import CapabilityManager
from emergence.security.security_manager import SecurityManager

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLUGINS_ROOT = PROJECT_ROOT / "plugins"


def create_kernel_context(
    executor: Executor | None = None,
    *,
    llm_provider: Any | None = None,
) -> KernelContext:
    """
    Construct and wire together every core kernel service.

    This is the composition root of EmergenceOS. Every service
    that forms part of the kernel is instantiated here and
    injected into the KernelContext.
    """

    event_store = EventStore()
    event_bus = PersistingEventBus(event_store)
    capabilities = CapabilityManager()
    security = SecurityManager(capabilities)
    budgets = BudgetTracker()

    scheduler = Scheduler(event_bus)
    state = StateStore(event_bus)
    registry = ProcessRegistry()
    process_table = ProcessTable()
    mailboxes = MailboxManager(event_bus)

    memory_store = MemoryStore()
    memory = MemoryManager(memory_store, event_bus)
    checkpoints = CheckpointManager.in_memory(
        event_bus,
        memory,
        budgets,
    )

    exec_ = executor if executor is not None else Executor()

    tool_registry = ToolRegistry()
    register_kernel_tools(
        tool_registry,
        memory=memory,
        llm_provider=llm_provider,
    )
    tools = ToolExecutor(
        tool_registry,
        event_bus,
        security,
        budgets,
    )

    observability = ObservabilityKernel(event_store, event_bus)
    cognitive = CognitiveManager(event_bus=event_bus)

    plugins = PluginManager(
        registry=registry,
        executor=exec_,
        event_bus=event_bus,
        plugins_root=PLUGINS_ROOT,
    )

    return KernelContext(
        event_bus=event_bus,
        event_store=event_store,
        state=state,
        scheduler=scheduler,
        registry=registry,
        process_table=process_table,
        mailboxes=mailboxes,
        capabilities=capabilities,
        security=security,
        budgets=budgets,
        memory=memory,
        checkpoints=checkpoints,
        executor=exec_,
        tools=tools,
        observability=observability,
        plugins=plugins,
        cognitive=cognitive,
    )


def build_kernel(
    *,
    spawn: str | None = "hello_world",
    enable_supervisor: bool = True,
    load_plugins: bool = True,
) -> Kernel:
    """
    Construct a fully wired Kernel from the composition root.

    Parameters
    ----------
    spawn:
        Name of a registered ProcessDefinition to spawn immediately.
        Pass None to skip automatic spawning.
    enable_supervisor:
        When True, attach the fault-tolerance supervisor.
    load_plugins:
        When True, auto-discover and load plugins from /plugins.
    """

    executor = Executor()
    ctx = create_kernel_context(executor=executor)
    lifecycle = LifecycleManager()

    if load_plugins:
        ctx.plugins.load_all()

    kernel = Kernel(
        ctx=ctx,
        executor=ctx.executor,
        lifecycle=lifecycle,
    )

    if enable_supervisor:
        Supervisor(
            kernel=kernel,
            checkpoints=ctx.checkpoints,
            event_store=ctx.event_store,
        )

    if spawn is not None:
        kernel.spawn(ctx.registry.get(spawn))

    return kernel


def build_system_model_demo() -> Kernel:
    """
    Construct a kernel wired for the system-model simulation.

    Spawns Coordinator, Researcher, and Evaluator processes that
    demonstrate M3 security and M4 scheduling in a multi-process
    research pipeline.
    """
    demo = "emergence.apps.system_model_demo"

    executor = Executor()
    ctx = create_kernel_context(executor=executor)
    lifecycle = LifecycleManager()

    from emergence.core.process_definition import ProcessDefinition
    from emergence.executor.python_runner import PythonRunner

    for entrypoint in (
        "run_researcher",
        "run_coordinator",
        "run_evaluator",
    ):
        executor.register_runner(
            f"{demo}:{entrypoint}",
            PythonRunner(),
        )

    definitions = {
        "researcher": ProcessDefinition(
            name="researcher",
            description="Receives research requests and responds.",
            implementation=f"{demo}:run_researcher",
            default_budget=ResourceBudget(max_execution_time_seconds=60),
        ),
        "coordinator": ProcessDefinition(
            name="coordinator",
            description="Orchestrates the research pipeline.",
            implementation=f"{demo}:run_coordinator",
            default_budget=ResourceBudget(max_execution_time_seconds=60),
        ),
        "evaluator": ProcessDefinition(
            name="evaluator",
            description="Evaluates research findings.",
            implementation=f"{demo}:run_evaluator",
            default_budget=ResourceBudget(max_execution_time_seconds=60),
        ),
    }

    for definition in definitions.values():
        ctx.registry.register(definition)

    kernel = Kernel(ctx=ctx, executor=ctx.executor, lifecycle=lifecycle)

    Supervisor(
        kernel=kernel,
        checkpoints=ctx.checkpoints,
        event_store=ctx.event_store,
    )

    researcher = kernel.spawn(definitions["researcher"], priority=5)
    kernel.spawn(definitions["coordinator"], priority=10)
    kernel.spawn(
        definitions["evaluator"],
        priority=3,
        depends_on=(researcher.process_id,),
    )

    ctx.state.set("researcher_pid", str(researcher.process_id))

    return kernel


def build_long_running_services() -> Kernel:
    """
    Boot a fleet of long-running service plugins.

    Spawns heartbeat, event_collector, two job_workers, and an
    orchestrator that drives them through a multi-phase scenario
    across many WAITING → READY cycles.
    """
    kernel = build_kernel(
        spawn=None,
        load_plugins=True,
        enable_supervisor=False,
    )
    ctx = kernel.context

    heartbeat = kernel.spawn(
        ctx.registry.get("heartbeat"),
        priority=8,
    )
    collector = kernel.spawn(
        ctx.registry.get("event_collector"),
        priority=7,
    )
    worker_def = ctx.registry.get("job_worker")
    worker_a = kernel.spawn(worker_def, priority=5)
    worker_b = kernel.spawn(worker_def, priority=5)

    ctx.state.set("svc:heartbeat", str(heartbeat.process_id))
    ctx.state.set("svc:collector", str(collector.process_id))
    ctx.state.set("svc:worker_a", str(worker_a.process_id))
    ctx.state.set("svc:worker_b", str(worker_b.process_id))
    ctx.state.set("max_beats", 50)

    kernel.spawn(
        ctx.registry.get("orchestrator"),
        priority=10,
    )

    return kernel


def build_plan_demo(topic: str) -> tuple[Kernel, "Goal", "Plan"]:
    """
    Boot kernel, run LLM planner for a goal, and return before execution.
    """
    from emergence.core.goal import Goal
    from emergence.core.plan import Plan

    kernel = build_kernel(spawn=None, load_plugins=True, enable_supervisor=True)
    goal, plan = kernel.create_plan_from_goal(topic)
    kernel.context.state.set("research_topic", topic)
    return kernel, goal, plan


def build_research_assistant(
    topic: str,
    *,
    auto_approve: bool = True,
) -> Kernel:
    """
    Boot the research assistant plugin for an end-to-end cognitive demo.
    """
    kernel = build_kernel(spawn=None, load_plugins=True, enable_supervisor=True)
    ctx = kernel.context

    ctx.state.set("research_topic", topic)
    ctx.state.set("auto_approve", auto_approve)

    kernel.spawn(
        ctx.registry.get("research_assistant"),
        priority=10,
    )

    return kernel
