from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from emergence.core.event import Event, EventType
from emergence.core.ids import ProcessID
from emergence.core.state import ProcessState
from emergence.security.capabilities import (
    capabilities_for_definition,
)

if TYPE_CHECKING:
    from emergence.checkpoint.checkpoint_manager import CheckpointManager
    from emergence.events.event_store import EventStore
    from emergence.kernel.kernel import Kernel


class RecoveryAction(str, Enum):
    RETRY = "retry"
    RESTORE = "restore"
    ESCALATE = "escalate"
    TERMINATE = "terminate"


@dataclass
class RecoveryDecision:
    action: RecoveryAction
    process_id: ProcessID
    reason: str
    delay_seconds: float = 0.0


@dataclass
class Supervisor:
    """
    Kernel-level supervisor for crash recovery and retries.

    Subscribes to PROCESS_FAILED and evaluates recovery policy
    using checkpoints and resource budgets.
    """

    kernel: Kernel
    checkpoints: CheckpointManager
    event_store: EventStore
    _retry_counts: dict[str, int] = field(default_factory=dict)
    _decisions: list[RecoveryDecision] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.kernel.context.event_bus.subscribe(
            EventType.PROCESS_FAILED,
            self._on_process_failed,
        )

    @property
    def decisions(self) -> tuple[RecoveryDecision, ...]:
        return tuple(self._decisions)

    def _on_process_failed(self, event: Event) -> None:
        if event.source_process is None:
            return

        process_id = event.source_process
        pid = str(process_id)

        try:
            process = self.kernel.get_process(process_id)
        except KeyError:
            return

        retries = self._retry_counts.get(pid, 0)
        max_retries = process.budget.max_retries

        checkpoint = self.checkpoints.latest_for_process(process_id)

        if checkpoint is not None:
            decision = RecoveryDecision(
                action=RecoveryAction.RESTORE,
                process_id=process_id,
                reason="Restoring from latest checkpoint before retry.",
            )
            self._decisions.append(decision)
            self._apply_restore(process_id, checkpoint.checkpoint_id)
            return

        if retries < max_retries:
            self._retry_counts[pid] = retries + 1
            delay = min(2 ** retries, 30)
            decision = RecoveryDecision(
                action=RecoveryAction.RETRY,
                process_id=process_id,
                reason=f"Retry {retries + 1}/{max_retries}",
                delay_seconds=delay,
            )
            self._decisions.append(decision)
            self._apply_retry(process)
            return

        decision = RecoveryDecision(
            action=RecoveryAction.TERMINATE,
            process_id=process_id,
            reason="Max retries exhausted.",
        )
        self._decisions.append(decision)

    def _apply_restore(
        self,
        process_id: ProcessID,
        checkpoint_id: str,
    ) -> None:
        process = self.kernel.get_process(process_id)
        self.checkpoints.restore_checkpoint(checkpoint_id, process)
        self._prepare_for_resume(process)
        self.kernel.context.budgets.record_retry(process_id)

    def _apply_retry(self, process) -> None:
        self._prepare_for_resume(process)
        self.kernel.context.budgets.record_retry(process.process_id)

    def _prepare_for_resume(self, process) -> None:
        pid = str(process.process_id)
        ctx = self.kernel.context

        if not ctx.mailboxes.exists(pid):
            ctx.mailboxes.create(pid)

        ctx.capabilities.clear(pid)
        for capability in capabilities_for_definition(process.definition):
            ctx.capabilities.grant(pid, capability)

        process.state = ProcessState.READY
        process.failure_reason = None
        process.completed_at = None
        ctx.scheduler.enqueue(process.process_id)
