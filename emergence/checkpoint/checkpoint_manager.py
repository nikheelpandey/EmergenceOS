from __future__ import annotations

from copy import deepcopy

from emergence.checkpoint.checkpoint import Checkpoint
from emergence.checkpoint.checkpoint_store import (
    CheckpointStore,
    InMemoryCheckpointStore,
)
from emergence.core.budget_tracker import BudgetTracker
from emergence.core.ids import ProcessID
from emergence.core.process import Process
from emergence.events.checkpoint_events import (
    CheckpointCreatedEvent,
    CheckpointRestoredEvent,
)
from emergence.events.event_bus import EventBus
from emergence.memory.memory_manager import MemoryManager


class CheckpointNotFoundError(Exception):
    """Raised when a requested checkpoint does not exist."""


class CheckpointManager:
    """
    Owns durable process snapshots enabling recovery.
    """

    def __init__(
        self,
        store: CheckpointStore,
        event_bus: EventBus,
        memory: MemoryManager,
        budgets: BudgetTracker,
    ) -> None:
        self._store = store
        self._event_bus = event_bus
        self._memory = memory
        self._budgets = budgets

    @classmethod
    def in_memory(
        cls,
        event_bus: EventBus,
        memory: MemoryManager,
        budgets: BudgetTracker,
    ) -> CheckpointManager:
        return cls(
            InMemoryCheckpointStore(),
            event_bus,
            memory,
            budgets,
        )

    def create_checkpoint(
        self,
        process: Process,
        *,
        event_offset: int = 0,
    ) -> Checkpoint:
        usage = deepcopy(
            self._budgets.usage(process.process_id)
        )
        checkpoint = Checkpoint(
            process_id=process.process_id,
            process_state=process.state,
            working_memory=self._memory.working_snapshot(
                process.process_id
            ),
            event_offset=event_offset,
            resource_usage=usage,
        )
        self._store.save(checkpoint)

        self._event_bus.publish(
            CheckpointCreatedEvent(
                checkpoint_id=checkpoint.checkpoint_id,
                process_id=process.process_id,
                source_process=process.process_id,
            )
        )
        return checkpoint

    def restore_checkpoint(
        self,
        checkpoint_id: str,
        process: Process,
    ) -> Checkpoint:
        checkpoint = self._store.get(checkpoint_id)
        if checkpoint is None:
            raise CheckpointNotFoundError(
                f"Checkpoint '{checkpoint_id}' not found."
            )

        for key, value in checkpoint.working_memory.items():
            self._memory.store(
                process.process_id,
                key,
                value,
            )

        usage = self._budgets.usage(process.process_id)
        usage.tokens = checkpoint.resource_usage.tokens
        usage.tool_invocations = (
            checkpoint.resource_usage.tool_invocations
        )
        usage.cost_usd = checkpoint.resource_usage.cost_usd
        usage.execution_seconds = (
            checkpoint.resource_usage.execution_seconds
        )
        usage.retries = checkpoint.resource_usage.retries

        self._event_bus.publish(
            CheckpointRestoredEvent(
                checkpoint_id=checkpoint.checkpoint_id,
                process_id=process.process_id,
                source_process=process.process_id,
            )
        )
        return checkpoint

    def latest_for_process(
        self,
        process_id: ProcessID,
    ) -> Checkpoint | None:
        return self._store.latest_for_process(str(process_id))
