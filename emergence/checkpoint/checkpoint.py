from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from emergence.core.budget_tracker import BudgetUsage
from emergence.core.ids import ProcessID
from emergence.core.state import ProcessState


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """
    Snapshot of recoverable process state.

    Contains sufficient information to resume execution without
    repeating completed work.
    """

    checkpoint_id: str = field(default_factory=lambda: str(uuid4()))
    process_id: ProcessID = field(default_factory=ProcessID.new)
    process_state: ProcessState = ProcessState.RUNNING
    working_memory: dict[str, Any] = field(default_factory=dict)
    event_offset: int = 0
    resource_usage: BudgetUsage = field(default_factory=BudgetUsage)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
