"""
Interactive command ingress for a running EmergenceOS kernel.

Accepts text commands on stdin (or programmatically) to spawn
plugins, create goals, and inspect the live system.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from emergence.kernel.kernel import Kernel


class KernelIngress:
    """
    Command handler for a persistent kernel instance.

    Commands
    --------
    help              Show available commands
    ps                List live processes
    spawn <plugin>    Spawn a plugin process
    goal <text>       Create goal + plan + execute (worker demo)
    research <topic>  Spawn research assistant for a topic
    plan <topic>      Run LLM planner and execute resulting plan
    approve <id>      Grant a pending user approval
    status            Show OS status and event count
    quit / exit       Request kernel shutdown
    """

    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel

    def handle(self, line: str) -> str | None:
        """
        Execute one command line.

        Returns a response string, or None to signal shutdown.
        """
        line = line.strip()
        if not line:
            return ""

        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        handlers = {
            "help": self._cmd_help,
            "?": self._cmd_help,
            "ps": self._cmd_ps,
            "spawn": lambda a: self._cmd_spawn(a),
            "goal": lambda a: self._cmd_goal(a),
            "research": lambda a: self._cmd_research(a),
            "plan": lambda a: self._cmd_plan(a),
            "approve": lambda a: self._cmd_approve(a),
            "status": self._cmd_status,
            "quit": lambda _: None,
            "exit": lambda _: None,
        }

        handler = handlers.get(cmd)
        if handler is None:
            return f"Unknown command: {cmd}. Type 'help'."

        return handler(arg)

    def run_repl(self, *, prompt: str = "eos> ") -> None:
        """Blocking read-eval loop on stdin."""
        print("EmergenceOS interactive shell. Type 'help' for commands.")
        while self._kernel.is_running:
            try:
                line = input(prompt)
            except EOFError:
                break
            result = self.handle(line)
            if result is None:
                self._kernel.shutdown()
                break
            if result:
                print(result)

    def run_repl_async(self, *, prompt: str = "eos> ") -> threading.Thread:
        """Start the REPL on a daemon thread."""
        thread = threading.Thread(
            target=self.run_repl,
            kwargs={"prompt": prompt},
            daemon=True,
            name="eos-ingress",
        )
        thread.start()
        return thread

    def _cmd_help(self, _: str = "") -> str:
        return (
            "Commands:\n"
            "  ps                  list processes\n"
            "  spawn <plugin>      spawn a plugin\n"
            "  goal <description>  cognitive goal demo\n"
            "  plan <topic>        LLM plan + execute\n"
            "  research <topic>  research assistant\n"
            "  approve <id>        grant user approval\n"
            "  status              OS status\n"
            "  quit                shutdown"
        )

    def _cmd_ps(self, _: str = "") -> str:
        lines = ["PID           NAME            STATE"]
        for proc in self._kernel.context.process_table.all():
            lines.append(
                f"{str(proc.process_id)[:12]}  "
                f"{proc.definition.name:<16}"
                f"{proc.state.value}"
            )
        return "\n".join(lines) if len(lines) > 1 else "(no processes)"

    def _cmd_spawn(self, name: str) -> str:
        if not name:
            return "Usage: spawn <plugin_name>"
        ctx = self._kernel.context
        try:
            definition = ctx.registry.get(name)
        except Exception as exc:
            return f"Plugin not found: {exc}"
        process = self._kernel.spawn(definition, priority=5)
        return f"Spawned {name} ({process.process_id})"

    def _cmd_goal(self, description: str) -> str:
        if not description:
            return "Usage: goal <description>"
        from emergence.cognitive.manager import TaskSpec

        goal = self._kernel.create_goal(description)
        self._kernel.start_planning(goal.goal_id)
        plan = self._kernel.create_plan(
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
        self._kernel.execute_plan(plan.plan_id)
        return f"Goal created: {description}"

    def _cmd_research(self, topic: str) -> str:
        if not topic:
            return "Usage: research <topic>"
        ctx = self._kernel.context
        ctx.state.set("research_topic", topic)
        ctx.state.set("auto_approve", True)
        process = self._kernel.spawn(
            ctx.registry.get("research_assistant"),
            priority=8,
        )
        return f"Research assistant spawned for: {topic} ({process.process_id})"

    def _cmd_plan(self, topic: str) -> str:
        if not topic:
            return "Usage: plan <topic>"
        ctx = self._kernel.context
        ctx.state.set("research_topic", topic)
        goal = self._kernel.create_goal(topic)
        self._kernel.start_planning(goal.goal_id)
        self._kernel.spawn_planner_for_goal(goal.goal_id)
        return (
            f"Planner spawned for: {topic}. "
            "Run completes when planner finishes; "
            "use 'status' to check plan_artifact."
        )

    def _cmd_approve(self, request_id: str) -> str:
        if not request_id:
            return "Usage: approve <request_id>"
        self._kernel.grant_user_approval(request_id)
        return f"Approval granted: {request_id}"

    def _cmd_status(self, _: str = "") -> str:
        ctx = self._kernel.context
        return (
            f"status={ctx.state.get('os:status', '?')}  "
            f"processes={self._kernel.process_count()}  "
            f"waiting={len(ctx.scheduler.waiting_ids())}  "
            f"queued={len(ctx.scheduler.queued_ids())}  "
            f"events={ctx.event_store.count()}"
        )
