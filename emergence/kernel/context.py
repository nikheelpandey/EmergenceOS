from __future__ import annotations

from dataclasses import dataclass

from emergence.checkpoint.checkpoint_manager import CheckpointManager
from emergence.cognitive.goal_registry import GoalRegistry
from emergence.cognitive.manager import CognitiveManager
from emergence.core.budget_tracker import BudgetTracker
from emergence.events.event_bus import EventBus
from emergence.events.event_store import EventStore
from emergence.executor.executor import Executor
from emergence.executor.tool_executor import ToolExecutor
from emergence.kernel.mailbox_manager import MailboxManager
from emergence.kernel.process_table import ProcessTable
from emergence.kernel.registry import ProcessRegistry
from emergence.kernel.state_store import StateStore
from emergence.memory.memory_manager import MemoryManager
from emergence.memory.knowledge_index import KnowledgeIndex
from emergence.observability.kernel import ObservabilityKernel
from emergence.plugins.manager import PluginManager
from emergence.scheduler.schedule_manager import ScheduleManager
from emergence.scheduler.scheduler import Scheduler
from emergence.security.capability_manager import CapabilityManager
from emergence.security.security_manager import SecurityManager
from emergence.spaces.registry import SpaceRegistry


@dataclass(frozen=True, slots=True)
class KernelContext:
    """
    The collection of kernel services available to processes.

    Rather than exposing the Kernel itself, processes receive a
    KernelContext containing references to the services they are
    allowed to interact with.
    """

    event_bus: EventBus
    event_store: EventStore
    state: StateStore
    scheduler: Scheduler
    registry: ProcessRegistry
    process_table: ProcessTable
    mailboxes: MailboxManager
    capabilities: CapabilityManager
    security: SecurityManager
    budgets: BudgetTracker
    memory: MemoryManager
    checkpoints: CheckpointManager
    executor: Executor
    tools: ToolExecutor
    observability: ObservabilityKernel
    plugins: PluginManager
    cognitive: CognitiveManager
    goal_registry: GoalRegistry
    knowledge_index: KnowledgeIndex
    space_registry: SpaceRegistry
    schedule_manager: ScheduleManager
