from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from emergence.memory.memory_store import MemoryStore


class FileMemoryStore(MemoryStore):
    """
    JSON file-backed memory store.

    Persists episodic and semantic memory to disk on every write.
    """

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists():
            raw = json.loads(self._path.read_text())
            if isinstance(raw, dict):
                self._memory = raw

    def set(self, key: str, value: Any) -> None:
        super().set(key, value)
        self._flush()

    def delete(self, key: str) -> None:
        super().delete(key)
        self._flush()

    def clear(self) -> None:
        super().clear()
        self._flush()

    def _flush(self) -> None:
        self._path.write_text(
            json.dumps(self._memory, indent=2, default=str) + "\n"
        )
