"""
observability/snapshot.py

Read-only snapshots of kernel runtime state for inspection and CLI tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from emergence.core.process import Process
from emergence.core.state import ProcessState
from emergence.kernel.kernel import Kernel


@dataclass(frozen=True, slots=True)
class ProcessSnapshot:
    """A point-in-time view of a single process."""

    process_id: str
    name: str
    state: ProcessState
    age_seconds: float
    parent_id: str | None
    scheduled: bool
    mailbox_pending: int
    capability_count: int
    failure_reason: str | None


@dataclass(frozen=True, slots=True)
class SystemSnapshot:
    """A point-in-time view of the entire kernel runtime."""

    captured_at: datetime
    processes: tuple[ProcessSnapshot, ...]
    scheduler_depth: int
    queued_process_ids: tuple[str, ...]
    state_keys: tuple[str, ...]

    @property
    def process_count(self) -> int:
        return len(self.processes)

    def count_by_state(self) -> dict[ProcessState, int]:
        counts: dict[ProcessState, int] = {}
        for process in self.processes:
            counts[process.state] = counts.get(process.state, 0) + 1
        return counts


def capture_system_snapshot(kernel: Kernel) -> SystemSnapshot:
    """
    Capture a read-only snapshot of the current kernel runtime.
    """

    ctx = kernel.context
    processes = tuple(
        _capture_process(kernel, process)
        for process in ctx.process_table.all()
    )

    return SystemSnapshot(
        captured_at=datetime.now(UTC),
        processes=processes,
        scheduler_depth=len(ctx.scheduler),
        queued_process_ids=tuple(
            str(process_id) for process_id in ctx.scheduler.queued_ids()
        ),
        state_keys=tuple(ctx.state.keys()),
    )


def _capture_process(kernel: Kernel, process: Process) -> ProcessSnapshot:
    pid = str(process.process_id)
    ctx = kernel.context

    return ProcessSnapshot(
        process_id=pid,
        name=process.definition.name,
        state=process.state,
        age_seconds=process.age_seconds,
        parent_id=(
            str(process.parent_process_id)
            if process.parent_process_id is not None
            else None
        ),
        scheduled=ctx.scheduler.contains(process.process_id),
        mailbox_pending=ctx.mailboxes.pending(pid),
        capability_count=len(ctx.capabilities.capabilities(pid)),
        failure_reason=process.failure_reason,
    )
