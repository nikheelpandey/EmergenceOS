"""
boot.py

Bootstraps the EmergenceOS runtime.

Responsibilities
----------------
- Construct infrastructure components
- Register execution backends
- Register process definitions
- Construct the Kernel
- Spawn the initial process
- Start the execution loop

This module intentionally contains no business logic.
"""

from emergence.core.budget import ResourceBudget
from emergence.core.process_definition import ProcessDefinition

from emergence.events.event_bus import EventBus

from emergence.executor.executor import Executor
from emergence.executor.python_runner import PythonRunner

from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.kernel.process_table import ProcessTable
from emergence.kernel.registry import ProcessRegistry

from emergence.scheduler.scheduler import Scheduler


def build_kernel() -> Kernel:
    """
    Construct the EmergenceOS kernel and all core infrastructure.
    """

    # -------------------------------------------------------------
    # Core Infrastructure
    # -------------------------------------------------------------

    event_bus = EventBus()

    process_table = ProcessTable()

    scheduler = Scheduler()

    executor = Executor()

    registry = ProcessRegistry()

    lifecycle = LifecycleManager()

    # -------------------------------------------------------------
    # Register Runners
    # -------------------------------------------------------------

    executor.register_runner(
        "emergence.apps.hello_world:run",
        PythonRunner(),
    )

    # -------------------------------------------------------------
    # Register Applications
    # -------------------------------------------------------------

    hello_world = ProcessDefinition(
        name="hello_world",
        description="Simple Hello World application.",
        implementation="emergence.apps.hello_world:run",
        default_budget=ResourceBudget(),
    )

    registry.register(hello_world)

    # -------------------------------------------------------------
    # Construct Kernel
    # -------------------------------------------------------------

    kernel = Kernel(
        event_bus=event_bus,
        process_table=process_table,
        scheduler=scheduler,
        executor=executor,
    )

    # -------------------------------------------------------------
    # Temporary bootstrap
    # -------------------------------------------------------------
    #
    # Until the Kernel owns a ProcessRegistry internally,
    # we manually retrieve the ProcessDefinition and spawn it.
    #

    kernel.spawn(
        registry.get("hello_world")
    )
    print(kernel.process_count())
    print(kernel.has_work())
    return kernel


def main() -> None:
    """
    Boot EmergenceOS.
    """

    print()
    print("=" * 60)
    print("Booting EmergenceOS...")
    print("=" * 60)
    print()

    kernel = build_kernel()

    kernel.run()

    print()
    print("=" * 60)
    print("EmergenceOS shutdown complete.")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()

    