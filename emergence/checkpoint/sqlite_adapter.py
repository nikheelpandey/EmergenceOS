"""
SQLite adapter stub for checkpoint persistence.

Full implementation deferred — provides the interface boundary
for durable checkpoint storage.
"""

from __future__ import annotations

from emergence.checkpoint.checkpoint import Checkpoint
from emergence.checkpoint.checkpoint_store import CheckpointStore


class SQLiteCheckpointStore(CheckpointStore):
    """
    Stub SQLite-backed checkpoint store.

    Raises NotImplementedError until a durable adapter is wired.
    """

    def __init__(self, db_path: str = "checkpoints.db") -> None:
        self._db_path = db_path

    def save(self, checkpoint: Checkpoint) -> None:
        raise NotImplementedError(
            "SQLite checkpoint persistence is not yet implemented. "
            f"Use InMemoryCheckpointStore instead. (path={self._db_path})"
        )

    def get(self, checkpoint_id: str) -> Checkpoint | None:
        raise NotImplementedError(
            "SQLite checkpoint persistence is not yet implemented."
        )

    def latest_for_process(self, process_id: str) -> Checkpoint | None:
        raise NotImplementedError(
            "SQLite checkpoint persistence is not yet implemented."
        )

    def list_for_process(self, process_id: str) -> list[Checkpoint]:
        raise NotImplementedError(
            "SQLite checkpoint persistence is not yet implemented."
        )
