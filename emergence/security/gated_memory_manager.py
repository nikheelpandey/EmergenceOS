from __future__ import annotations

from typing import Any

from emergence.core.ids import ProcessID
from emergence.memory.memory_category import MemoryCategory
from emergence.memory.memory_manager import MemoryManager
from emergence.security.capabilities import MEMORY_READ, MEMORY_WRITE
from emergence.security.security_manager import SecurityManager


class GatedMemoryManager:
    """
    Capability-gated facade over the MemoryManager.
    """

    def __init__(
        self,
        memory: MemoryManager,
        security: SecurityManager,
        process_id: ProcessID,
    ) -> None:
        self._memory = memory
        self._security = security
        self._process_id = process_id
        pid = str(process_id)

        self._pid = pid

    def store(
        self,
        key: str,
        value: Any,
        *,
        category: MemoryCategory = MemoryCategory.WORKING,
    ) -> None:
        self._security.require(
            self._pid,
            MEMORY_WRITE,
            operation=f"memory.store('{key}')",
        )
        self._memory.store(
            self._process_id,
            key,
            value,
            category=category,
        )

    def retrieve(
        self,
        key: str,
        *,
        category: MemoryCategory = MemoryCategory.WORKING,
        default: Any = None,
    ) -> Any:
        self._security.require(
            self._pid,
            MEMORY_READ,
            operation=f"memory.retrieve('{key}')",
        )
        return self._memory.retrieve(
            self._process_id,
            key,
            category=category,
            default=default,
        )

    def delete(
        self,
        key: str,
        *,
        category: MemoryCategory = MemoryCategory.WORKING,
    ) -> None:
        self._security.require(
            self._pid,
            MEMORY_WRITE,
            operation=f"memory.delete('{key}')",
        )
        self._memory.delete(
            self._process_id,
            key,
            category=category,
        )

    def exists(
        self,
        key: str,
        *,
        category: MemoryCategory = MemoryCategory.WORKING,
    ) -> bool:
        self._security.require(
            self._pid,
            MEMORY_READ,
            operation=f"memory.exists('{key}')",
        )
        return self._memory.exists(
            self._process_id,
            key,
            category=category,
        )
