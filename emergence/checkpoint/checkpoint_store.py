from __future__ import annotations

from abc import ABC, abstractmethod

from emergence.checkpoint.checkpoint import Checkpoint


class CheckpointStore(ABC):
    """Abstract persistence layer for checkpoints."""

    @abstractmethod
    def save(self, checkpoint: Checkpoint) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, checkpoint_id: str) -> Checkpoint | None:
        raise NotImplementedError

    @abstractmethod
    def latest_for_process(
        self,
        process_id: str,
    ) -> Checkpoint | None:
        raise NotImplementedError

    @abstractmethod
    def list_for_process(self, process_id: str) -> list[Checkpoint]:
        raise NotImplementedError


class InMemoryCheckpointStore(CheckpointStore):
    """In-memory checkpoint store for development and tests."""

    def __init__(self) -> None:
        self._checkpoints: dict[str, Checkpoint] = {}
        self._by_process: dict[str, list[str]] = {}

    def save(self, checkpoint: Checkpoint) -> None:
        self._checkpoints[checkpoint.checkpoint_id] = checkpoint
        pid = str(checkpoint.process_id)
        self._by_process.setdefault(pid, []).append(
            checkpoint.checkpoint_id
        )

    def get(self, checkpoint_id: str) -> Checkpoint | None:
        return self._checkpoints.get(checkpoint_id)

    def latest_for_process(self, process_id: str) -> Checkpoint | None:
        ids = self._by_process.get(process_id, [])
        if not ids:
            return None
        return self._checkpoints[ids[-1]]

    def list_for_process(self, process_id: str) -> list[Checkpoint]:
        return [
            self._checkpoints[cid]
            for cid in self._by_process.get(process_id, [])
            if cid in self._checkpoints
        ]

    def clear(self) -> None:
        self._checkpoints.clear()
        self._by_process.clear()
