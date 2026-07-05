"""
boot.py

Bootstraps the EmergenceOS runtime.

Default: persistent OS — all plugins, platform services, interactive
shell. Runs until Ctrl+C.

Use --once for batch demos that drain and exit.
"""

import sys

from emergence.cognitive.manager import TaskSpec
from emergence.cognitive.goal_registry import GoalKind
from emergence.apps.research_output import format_research_output
from emergence.kernel.boot_context import (
    build_kernel,
    build_long_running_services,
    build_plan_demo,
    build_research_assistant,
    build_system_model_demo,
)
from emergence.kernel.ingress import KernelIngress
from emergence.kernel.runtime import build_runtime


def _arg_value(flag: str) -> str | None:
    if flag not in sys.argv:
        return None
    idx = sys.argv.index(flag)
    if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("-"):
        return sys.argv[idx + 1]
    return None


def build_cognitive_demo():
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
    once = "--once" in sys.argv
    no_repl = "--no-repl" in sys.argv
    demo = "--demo" in sys.argv
    goal = "--goal" in sys.argv
    services = "--services" in sys.argv
    hello = "--hello" in sys.argv
    plan_topic = _arg_value("--plan")
    research_topic = _arg_value("--research")

    batch = once or demo or goal or services or hello or plan_topic or research_topic

    print()
    print("=" * 60)
    if batch:
        print("EmergenceOS — Batch Mode (--once)")
    else:
        print("EmergenceOS — Persistent Runtime")
        print("Ctrl+C to shutdown.")
    print("=" * 60)
    print()

    goal_obj = plan_obj = None

    if batch:
        if demo:
            kernel = build_system_model_demo()
        elif goal:
            kernel, goal_obj, plan_obj = build_cognitive_demo()
        elif services:
            kernel = build_long_running_services()
        elif plan_topic:
            kernel, goal_obj, plan_obj = build_plan_demo(plan_topic)
            kernel.execute_plan(plan_obj.plan_id)
        elif research_topic:
            kernel, goal_obj = build_research_assistant(research_topic)
        elif hello:
            kernel = build_kernel(spawn="hello_world")
        else:
            kernel = build_kernel()
        kernel.run()
    else:
        kernel = build_runtime()

        if plan_topic:
            kernel.context.state.set("research_topic", plan_topic)
            goal_obj = kernel.create_goal(plan_topic)
            kernel.start_planning(goal_obj.goal_id)
            kernel.spawn_planner_for_goal(goal_obj.goal_id)
        elif research_topic:
            kernel.context.state.set("research_topic", research_topic)
            kernel.context.state.set("auto_approve", True)
            goal_obj = kernel.create_goal(
                f"Research: {research_topic}",
                kind=GoalKind.PERSISTENT,
            )
            kernel.spawn(
                kernel.context.registry.get("research_assistant"),
                goal_id=goal_obj.goal_id,
                priority=8,
            )
        elif goal:
            goal_obj = kernel.create_goal("Write technical report")
            kernel.start_planning(goal_obj.goal_id)
            plan_obj = kernel.create_plan(
                goal_obj.goal_id,
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
            kernel.execute_plan(plan_obj.plan_id)

        if not no_repl and sys.stdin.isatty():
            KernelIngress(kernel).run_repl_async()
            print("Platform services: heartbeat, event_collector, job_worker")
            print("Interactive shell ready — type 'help'.\n")

        kernel.run_forever()

    if research_topic:
        print(format_research_output(kernel))
        print()

    print()
    print("=" * 60)
    print(f"Events: {kernel.context.event_store.count()}  "
          f"Processes: {kernel.process_count()}")
    if goal_obj:
        print(f"Goal: {goal_obj.state.value}")
    if plan_obj:
        print(f"Plan: {plan_obj.state.value}")
    print("EmergenceOS shutdown complete.")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
