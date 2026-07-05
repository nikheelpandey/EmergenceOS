"""
Shared test helpers for building ProcessContext in unit tests.
"""

from __future__ import annotations

from emergence.checkpoint.checkpoint_manager import CheckpointManager
from emergence.core.budget_tracker import BudgetTracker
from emergence.core.ids import GoalID, ProcessID
from emergence.core.process_context import ProcessContext
from emergence.core.process_definition import ProcessDefinition
from emergence.events.event_bus import EventBus
from emergence.executor.tool_executor import ToolExecutor, ToolRegistry
from emergence.kernel.mailbox_manager import MailboxManager
from emergence.kernel.process_table import ProcessTable
from emergence.kernel.state_store import StateStore
from emergence.memory.memory_manager import MemoryManager
from emergence.memory.memory_store import MemoryStore
from emergence.security.capability_manager import CapabilityManager
from emergence.security.gated_checkpoint_manager import (
    GatedCheckpointManager,
)
from emergence.security.gated_event_bus import GatedEventBus
from emergence.security.gated_mailbox_manager import GatedMailboxManager
from emergence.security.gated_memory_manager import GatedMemoryManager
from emergence.security.gated_state_store import GatedStateStore
from emergence.security.gated_tool_access import GatedToolAccess
from emergence.security.security_manager import SecurityManager
from emergence.security.capabilities import DEFAULT_PROCESS_CAPABILITIES


def build_test_process_context(
    definition: ProcessDefinition,
    *,
    process_id: ProcessID | None = None,
    goal_id: GoalID | None = None,
    event_bus: EventBus | None = None,
) -> ProcessContext:
    """Construct a fully wired ProcessContext for unit tests."""
    bus = event_bus or EventBus()
    state = StateStore(bus)
    mailboxes = MailboxManager(bus)
    capabilities = CapabilityManager()
    security = SecurityManager(capabilities)
    budgets = BudgetTracker()
    memory = MemoryManager(MemoryStore(), bus)
    checkpoints = CheckpointManager.in_memory(bus, memory, budgets)
    tools = ToolExecutor(ToolRegistry(), bus, security, budgets)
    process_table = ProcessTable()

    pid = process_id or ProcessID.new()
    pid_str = str(pid)

    for cap in DEFAULT_PROCESS_CAPABILITIES:
        capabilities.grant(pid_str, cap)

    return ProcessContext(
        process_id=pid,
        goal_id=goal_id,
        definition=definition,
        state=GatedStateStore(state, security, pid_str),
        memory=GatedMemoryManager(memory, security, pid),
        event_bus=GatedEventBus(bus, security, pid_str),
        mailboxes=GatedMailboxManager(mailboxes, security, pid_str),
        checkpoints=GatedCheckpointManager(
            checkpoints,
            security,
            pid,
            process_table.get,
        ),
        tools=GatedToolAccess(tools, security, pid),
        _mailbox_manager=mailboxes,
    )
