from __future__ import annotations

from emergence.checkpoint.checkpoint_manager import CheckpointManager
from emergence.core.ids import ProcessID
from emergence.security.capabilities import (
    CHECKPOINT_CREATE,
    CHECKPOINT_RESTORE,
)
from emergence.security.security_manager import SecurityManager


class GatedCheckpointManager:
    """Capability-gated facade over CheckpointManager."""

    def __init__(
        self,
        checkpoints: CheckpointManager,
        security: SecurityManager,
        process_id: ProcessID,
        process_getter,
    ) -> None:
        self._checkpoints = checkpoints
        self._security = security
        self._process_id = process_id
        self._process_getter = process_getter
        self._pid = str(process_id)

    def create(self) -> str:
        self._security.require(
            self._pid,
            CHECKPOINT_CREATE,
            operation="checkpoint.create",
        )
        process = self._process_getter(self._process_id)
        checkpoint = self._checkpoints.create_checkpoint(process)
        return checkpoint.checkpoint_id

    def restore(self, checkpoint_id: str) -> None:
        self._security.require(
            self._pid,
            CHECKPOINT_RESTORE,
            operation="checkpoint.restore",
        )
        process = self._process_getter(self._process_id)
        self._checkpoints.restore_checkpoint(checkpoint_id, process)
