from __future__ import annotations

from dataclasses import dataclass

from emergence.checkpoint.checkpoint_manager import CheckpointManager
from emergence.core.budget_tracker import BudgetTracker
from emergence.core.ids import GoalID, ProcessID
from emergence.core.process_definition import ProcessDefinition
from emergence.core.process_waiting import ProcessWaiting
from emergence.core.wait_condition import WaitCondition
from emergence.core.wait_conditions import (
    ApprovalWaitCondition,
    MessageWaitCondition,
)
from emergence.events.user_events import UserApprovalRequestedEvent
from emergence.kernel.state_store import StateStore
from emergence.events.event_store import EventStore
from emergence.executor.tool_executor import ToolExecutor
from emergence.kernel.mailbox_manager import MailboxManager
from emergence.memory.memory_manager import MemoryManager
from emergence.observability.kernel import ObservabilityKernel
from emergence.security.gated_checkpoint_manager import (
    GatedCheckpointManager,
)
from emergence.security.gated_event_bus import GatedEventBus
from emergence.security.gated_mailbox_manager import GatedMailboxManager
from emergence.security.gated_memory_manager import GatedMemoryManager
from emergence.security.gated_state_store import GatedStateStore
from emergence.security.gated_tool_access import GatedToolAccess


@dataclass(frozen=True, slots=True)
class ProcessContext:
    """
    Runtime context provided to every executing process.

    The ProcessContext gives a process access to the kernel
    services it is permitted to use without exposing the
    entire Kernel implementation.

    All exposed services are capability-gated facades.
    """

    process_id: ProcessID
    goal_id: GoalID | None
    definition: ProcessDefinition

    state: GatedStateStore
    memory: GatedMemoryManager
    event_bus: GatedEventBus
    mailboxes: GatedMailboxManager
    checkpoints: GatedCheckpointManager
    tools: GatedToolAccess
    _mailbox_manager: MailboxManager
    _state_store: StateStore

    def wait(self, condition: WaitCondition) -> None:
        """
        Yield execution until the scheduler satisfies the condition.

        Raises
        ------
        ProcessWaiting
            Always — the kernel catches this and transitions to WAITING.
        """
        raise ProcessWaiting(condition)

    def wait_for_message(self) -> None:
        """Yield until a message arrives in this process's mailbox."""
        self.wait(
            MessageWaitCondition(
                str(self.process_id),
                self._mailbox_manager,
            )
        )

    def wait_for_approval(
        self,
        request_id: str,
        *,
        message: str = "",
    ) -> None:
        """
        Yield until a user grants approval for the given request.

        Publishes USER_APPROVAL_REQUESTED and checkpoints on WAITING.
        """
        self.event_bus.publish(
            UserApprovalRequestedEvent(
                request_id=request_id,
                message=message,
                source_process=self.process_id,
                payload={
                    "request_id": request_id,
                    "message": message,
                },
            )
        )
        self.wait(ApprovalWaitCondition(request_id, self._state_store))
