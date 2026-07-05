"""
EmergenceOS command-line tools.

Usage
-----
    python -m emergence.cli ps
    python -m emergence.cli top
    python -m emergence.cli sched
    python -m emergence.cli state

Add --demo to inspect a sample kernel with mixed process states.
"""

from __future__ import annotations

import argparse
import sys
import time

from emergence.kernel.kernel import Kernel
from emergence.kernel.boot_context import build_kernel
from emergence.observability.demo import build_demo_kernel
from emergence.observability.display import (
    format_process_table,
    format_scheduler_view,
    format_state_view,
    format_system_header,
    format_top_screen,
)
from emergence.observability.snapshot import capture_system_snapshot


def format_budget_view(kernel: Kernel) -> str:
    lines = ["BUDGET USAGE", "─" * 40]
    for process in kernel.context.process_table.all():
        usage = kernel.context.budgets.usage(process.process_id)
        lines.append(
            f"  {process.definition.name:<16} "
            f"tokens={usage.tokens} "
            f"tools={usage.tool_invocations} "
            f"time={usage.execution_seconds:.2f}s "
            f"retries={usage.retries}"
        )
    if len(lines) == 2:
        lines.append("  (no processes)")
    return "\n".join(lines)


def format_trace_view(kernel: Kernel, correlation_id: str) -> str:
    from uuid import UUID

    events = kernel.context.observability.trace.trace(
        UUID(correlation_id)
    )
    lines = [f"TRACE {correlation_id}", "─" * 40]
    for event in events:
        lines.append(
            f"  {event.timestamp.isoformat()} "
            f"{event.event_type.value} "
            f"pid={event.source_process}"
        )
    if len(lines) == 2:
        lines.append("  (no events)")
    return "\n".join(lines)


def format_metrics_view(kernel: Kernel) -> str:
    metrics = kernel.context.observability.metrics.collect(kernel)
    lines = ["METRICS", "─" * 40]
    lines.append(f"  events:     {metrics.event_throughput}")
    lines.append(f"  queue:      {metrics.scheduler_depth}")
    lines.append(f"  waiting:    {metrics.waiting_count}")
    lines.append(f"  tokens:     {metrics.token_consumption}")
    for state, count in sorted(metrics.process_count_by_state.items()):
        lines.append(f"  {state}: {count}")
    return "\n".join(lines)

_CLEAR_SCREEN = "\033[2J\033[H"


def _resolve_kernel(args: argparse.Namespace) -> Kernel:
    if args.demo:
        return build_demo_kernel()
    return build_kernel(spawn=None)


def cmd_ps(args: argparse.Namespace) -> int:
    kernel = _resolve_kernel(args)
    snapshot = capture_system_snapshot(kernel)

    print(format_system_header(snapshot))
    print()
    print(format_process_table(snapshot, wide=args.wide))
    return 0


def cmd_top(args: argparse.Namespace) -> int:
    kernel = _resolve_kernel(args)

    try:
        while True:
            snapshot = capture_system_snapshot(kernel)
            if sys.stdout.isatty():
                sys.stdout.write(_CLEAR_SCREEN)
            print(format_top_screen(snapshot, wide=args.wide))
            if args.once:
                break
            if sys.stdout.isatty():
                print("\nPress Ctrl+C to quit")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        if sys.stdout.isatty():
            print()

    return 0


def cmd_sched(args: argparse.Namespace) -> int:
    kernel = _resolve_kernel(args)
    snapshot = capture_system_snapshot(kernel)

    print(format_system_header(snapshot))
    print()
    print(format_scheduler_view(snapshot))
    return 0


def cmd_state(args: argparse.Namespace) -> int:
    kernel = _resolve_kernel(args)
    snapshot = capture_system_snapshot(kernel)
    state = kernel.context.state.snapshot()

    print(format_system_header(snapshot))
    print()
    print(format_state_view(snapshot, state))
    return 0


def cmd_budget(args: argparse.Namespace) -> int:
    kernel = _resolve_kernel(args)
    snapshot = capture_system_snapshot(kernel)
    print(format_system_header(snapshot))
    print()
    print(format_budget_view(kernel))
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    kernel = _resolve_kernel(args)
    print(format_trace_view(kernel, args.correlation_id))
    return 0


def cmd_metrics(args: argparse.Namespace) -> int:
    kernel = _resolve_kernel(args)
    snapshot = capture_system_snapshot(kernel)
    print(format_system_header(snapshot))
    print()
    print(format_metrics_view(kernel))
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    kernel = _resolve_kernel(args)
    kernel.grant_user_approval(args.request_id)
    print(f"Approval granted for request {args.request_id}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from emergence.kernel.ingress import KernelIngress
    from emergence.kernel.runtime import build_runtime

    kernel = build_runtime()
    print("EmergenceOS persistent runtime started.")
    print("Platform services: heartbeat, event_collector, job_worker")
    print("Ctrl+C to shutdown.\n")

    if sys.stdin.isatty() and not args.no_repl:
        KernelIngress(kernel).run_repl_async()

    kernel.run_forever()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eos",
        description="EmergenceOS kernel observability tools",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    ps = subparsers.add_parser(
        "ps",
        help="list processes (like ps)",
    )
    ps.add_argument(
        "--demo",
        action="store_true",
        help="inspect a built-in demo kernel with mixed process states",
    )
    ps.add_argument(
        "--wide",
        action="store_true",
        help="show parent PID and failure reason",
    )
    ps.set_defaults(func=cmd_ps)

    top = subparsers.add_parser(
        "top",
        help="live process monitor (like top/htop)",
    )
    top.add_argument(
        "--demo",
        action="store_true",
        help="inspect a built-in demo kernel with mixed process states",
    )
    top.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="refresh interval in seconds (default: 1.0)",
    )
    top.add_argument(
        "--once",
        action="store_true",
        help="render a single frame and exit",
    )
    top.add_argument(
        "--wide",
        action="store_true",
        help="show parent PID and failure reason",
    )
    top.set_defaults(func=cmd_top)

    sched = subparsers.add_parser(
        "sched",
        help="show scheduler ready queue",
    )
    sched.add_argument(
        "--demo",
        action="store_true",
        help="inspect a built-in demo kernel with mixed process states",
    )
    sched.set_defaults(func=cmd_sched)

    state = subparsers.add_parser(
        "state",
        help="dump shared runtime state",
    )
    state.add_argument(
        "--demo",
        action="store_true",
        help="inspect a built-in demo kernel with mixed process states",
    )
    state.set_defaults(func=cmd_state)

    budget = subparsers.add_parser(
        "budget",
        help="show per-process budget usage",
    )
    budget.add_argument("--demo", action="store_true")
    budget.set_defaults(func=cmd_budget)

    trace = subparsers.add_parser(
        "trace",
        help="trace event chain by correlation_id",
    )
    trace.add_argument("correlation_id")
    trace.add_argument("--demo", action="store_true")
    trace.set_defaults(func=cmd_trace)

    metrics = subparsers.add_parser(
        "metrics",
        help="show system metrics",
    )
    metrics.add_argument("--demo", action="store_true")
    metrics.set_defaults(func=cmd_metrics)

    approve = subparsers.add_parser(
        "approve",
        help="grant user approval for a pending request",
    )
    approve.add_argument("request_id")
    approve.add_argument("--demo", action="store_true")
    approve.set_defaults(func=cmd_approve)

    serve = subparsers.add_parser(
        "serve",
        help="start persistent EmergenceOS runtime",
    )
    serve.add_argument(
        "--no-repl",
        action="store_true",
        help="disable interactive shell",
    )
    serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
