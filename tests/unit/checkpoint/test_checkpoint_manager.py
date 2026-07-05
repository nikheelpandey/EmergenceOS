"""Tests for emergence.checkpoint — M6."""

from __future__ import annotations

from emergence.checkpoint.checkpoint_manager import (
    CheckpointManager,
    CheckpointNotFoundError,
)
from emergence.core.event import EventType
from emergence.core.ids import ProcessID
from emergence.core.process import Process
from emergence.core.process_definition import ProcessDefinition
from emergence.core.state import ProcessState
from emergence.events.event_bus import EventBus
from emergence.memory.memory_manager import MemoryManager
from emergence.memory.memory_store import MemoryStore
from emergence.core.budget_tracker import BudgetTracker
import pytest


class TestCheckpointManager:
    def test_create_and_restore_checkpoint(self):
        bus = EventBus()
        events = []
        bus.subscribe(
            EventType.CHECKPOINT_CREATED,
            lambda e: events.append(e),
        )
        bus.subscribe(
            EventType.CHECKPOINT_RESTORED,
            lambda e: events.append(e),
        )

        memory = MemoryManager(MemoryStore(), bus)
        budgets = BudgetTracker()
        mgr = CheckpointManager.in_memory(bus, memory, budgets)

        definition = ProcessDefinition(
            name="worker",
            implementation="worker",
            version="1.0.0",
        )
        process = Process(definition=definition, state=ProcessState.RUNNING)
        memory.store(process.process_id, "step", 3)

        checkpoint = mgr.create_checkpoint(process)
        memory.store(process.process_id, "step", 99)

        mgr.restore_checkpoint(checkpoint.checkpoint_id, process)

        assert memory.retrieve(process.process_id, "step") == 3
        assert len(events) == 2

    def test_restore_missing_raises(self):
        bus = EventBus()
        memory = MemoryManager(MemoryStore(), bus)
        budgets = BudgetTracker()
        mgr = CheckpointManager.in_memory(bus, memory, budgets)

        definition = ProcessDefinition(
            name="x",
            implementation="x",
            version="1.0.0",
        )
        process = Process(definition=definition)

        with pytest.raises(CheckpointNotFoundError):
            mgr.restore_checkpoint("missing", process)
