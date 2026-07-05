"""
observability/display.py

Terminal formatters for kernel observability output.
"""

from __future__ import annotations

import sys

from emergence.core.state import ProcessState
from emergence.observability.snapshot import ProcessSnapshot, SystemSnapshot

_STATE_COLORS: dict[ProcessState, str] = {
    ProcessState.RUNNING: "\033[1;32m",
    ProcessState.READY: "\033[1;33m",
    ProcessState.WAITING: "\033[36m",
    ProcessState.BLOCKED: "\033[35m",
    ProcessState.COMPLETED: "\033[2m",
    ProcessState.FAILED: "\033[1;31m",
    ProcessState.CANCELLED: "\033[31m",
    ProcessState.CREATED: "\033[90m",
}

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"


def _short_id(value: str, length: int = 8) -> str:
    return value[:length]


def _use_color() -> bool:
    return sys.stdout.isatty()


def _colorize_state(state: ProcessState, text: str) -> str:
    if not _use_color():
        return text
    return f"{_STATE_COLORS.get(state, '')}{text}{_RESET}"


def format_process_table(
    snapshot: SystemSnapshot,
    *,
    wide: bool = False,
) -> str:
    """
    Render a process table similar to ps/top output.
    """

    if not snapshot.processes:
        return "  (no processes)"

    headers = (
        "PID",
        "NAME",
        "STATE",
        "AGE",
        "SCHED",
        "MAIL",
        "CAPS",
    )
    if wide:
        headers = headers + ("PARENT", "FAILURE")

    sorted_processes = sorted(snapshot.processes, key=lambda item: item.name)
    rows: list[tuple[str, ...]] = []
    for process in sorted_processes:
        row = (
            _short_id(process.process_id),
            process.name[:16],
            process.state.value,
            f"{process.age_seconds:6.1f}s",
            "yes" if process.scheduled else "no",
            str(process.mailbox_pending),
            str(process.capability_count),
        )
        if wide:
            parent = (
                _short_id(process.parent_id)
                if process.parent_id is not None
                else "-"
            )
            failure = (process.failure_reason or "-")[:24]
            row = row + (parent, failure)
        rows.append(row)

    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]

    lines = [_format_row(headers, widths, bold=True)]
    lines.append(_format_divider(widths))

    for process, row in zip(sorted_processes, rows, strict=True):
        colored_row = list(row)
        colored_row[2] = _colorize_state(process.state, row[2])
        lines.append(_format_row(colored_row, widths))

    return "\n".join(lines)


def format_system_header(snapshot: SystemSnapshot) -> str:
    """Render summary header for top-style views."""

    counts = snapshot.count_by_state()
    count_parts = [
        f"{state.value}={count}"
        for state, count in sorted(
            counts.items(),
            key=lambda item: item[0].value,
        )
    ]

    captured = snapshot.captured_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    summary = (
        f"EmergenceOS process monitor"
        f"  |  processes={snapshot.process_count}"
        f"  |  queue={snapshot.scheduler_depth}"
    )
    if count_parts:
        summary += f"  |  {', '.join(count_parts)}"
    summary += f"\n{_DIM}captured {captured}{_RESET}" if _use_color() else f"\ncaptured {captured}"
    return summary


def format_scheduler_view(snapshot: SystemSnapshot) -> str:
    """Render the scheduler ready queue."""

    if not snapshot.queued_process_ids:
        return "  (scheduler empty)"

    lines = ["READY QUEUE", "-----------"]
    for index, process_id in enumerate(snapshot.queued_process_ids, start=1):
        lines.append(f"  {index:>2}. {_short_id(process_id)}")
    return "\n".join(lines)


def format_state_view(snapshot: SystemSnapshot, kernel_state: dict) -> str:
    """Render shared runtime state keys and values."""

    if not kernel_state:
        return "  (state store empty)"

    lines = ["STATE STORE", "-----------"]
    for key in sorted(kernel_state):
        value = kernel_state[key]
        lines.append(f"  {key} = {value!r}")
    return "\n".join(lines)


def format_top_screen(
    snapshot: SystemSnapshot,
    *,
    wide: bool = False,
) -> str:
    """Render a full top-style screen."""

    sections = [
        format_system_header(snapshot),
        "",
        format_process_table(snapshot, wide=wide),
        "",
        format_scheduler_view(snapshot),
    ]
    return "\n".join(sections)


def _format_row(
    cells: tuple[str, ...] | list[str],
    widths: list[int],
    *,
    bold: bool = False,
) -> str:
    rendered = [
        f"{cell:<{widths[index]}}"
        for index, cell in enumerate(cells)
    ]
    line = "  ".join(rendered)
    if bold and _use_color():
        return f"{_BOLD}{line}{_RESET}"
    return line


def _format_divider(widths: list[int]) -> str:
    if _use_color():
        return f"{_DIM}{'  '.join('-' * width for width in widths)}{_RESET}"
    return "  ".join("-" * width for width in widths)
