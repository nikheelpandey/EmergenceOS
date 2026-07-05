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

import sys

from emergence.cognitive.manager import TaskSpec
from emergence.core.state import GoalState
from emergence.kernel.boot_context import (
    build_kernel,
    build_long_running_services,
    build_system_model_demo,
)


def build_cognitive_demo():
    """Run a Goal → Plan → Tasks pipeline using the worker plugin."""
    kernel = build_kernel(spawn=None, load_plugins=True, enable_supervisor=False)

    goal = kernel.create_goal("Write technical report")
    kernel.start_planning(goal.goal_id)

    plan = kernel.create_plan(
        goal.goal_id,
        [
            TaskSpec("research", "worker", priority=5),
            TaskSpec(
                "summarize",
                "worker",
                dependencies=("research",),
                priority=3,
            ),
        ],
    )
    kernel.execute_plan(plan.plan_id)
    return kernel, goal, plan


def main() -> None:
    """
    Boot EmergenceOS.

    Usage
    -----
    python boot.py              # hello_world plugin
    python boot.py --demo       # system-model simulation
    python boot.py --goal       # cognitive Goal → Plan → Tasks demo
    python boot.py --services   # long-running service fleet demo
    """
    demo_mode = "--demo" in sys.argv
    goal_mode = "--goal" in sys.argv
    services_mode = "--services" in sys.argv

    print()
    print("=" * 60)
    if demo_mode:
        print("Booting EmergenceOS — System Model Simulation")
    elif goal_mode:
        print("Booting EmergenceOS — Cognitive Goal Demo")
    elif services_mode:
        print("Booting EmergenceOS — Long-Running Services")
    else:
        print("Booting EmergenceOS...")
    print("=" * 60)
    print()

    if demo_mode:
        kernel = build_system_model_demo()
    elif goal_mode:
        kernel, goal, plan = build_cognitive_demo()
    elif services_mode:
        kernel = build_long_running_services()
    else:
        kernel = build_kernel()

    kernel.run()

    if services_mode:
        state = kernel.context.state
        print()
        print("Orchestrator:", state.get("orchestrator_status"))
        print("Heartbeat:", state.get("heartbeat"))
        print("Events collected:", state.get("events_collected"))
        print("Waiting processes:", len(kernel.context.scheduler.waiting_ids()))
        print("Event log size:", kernel.context.event_store.count(), "events")
    elif goal_mode:
        print()
        print("Goal state:", goal.state.value)
        print("Plan state:", plan.state.value)
    elif demo_mode:
        state = kernel.context.state
        print()
        print("Pipeline status:", state.get("pipeline_status"))
        print("Research:", state.get("research_findings", "—")[:80])
        print("Evaluation:", state.get("evaluation", "—"))

    print()
    print("=" * 60)
    print("EmergenceOS shutdown complete.")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
