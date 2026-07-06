from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from emergence.kernel.context import KernelContext
    from emergence.kernel.kernel import Kernel


@dataclass
class ToolServices:
    """
    Shared kernel services available to OS tool handlers.

    Populated in two phases: ``bind(ctx)`` after KernelContext exists,
    then ``bind_kernel(kernel)`` when spawn/scheduling tools need it.
    """

    knowledge_index: Any | None = None
    artifact_service: Any | None = None
    event_store: Any | None = None
    state: Any | None = None
    process_table: Any | None = None
    goal_registry: Any | None = None
    schedule_manager: Any | None = None
    registry: Any | None = None
    budgets: Any | None = None
    _kernel: Kernel | None = field(default=None, repr=False)

    def bind(self, ctx: KernelContext) -> None:
        self.knowledge_index = ctx.knowledge_index
        self.artifact_service = ctx.artifact_service
        self.event_store = ctx.event_store
        self.state = ctx.state
        self.process_table = ctx.process_table
        self.goal_registry = ctx.goal_registry
        self.schedule_manager = ctx.schedule_manager
        self.registry = ctx.registry
        self.budgets = ctx.budgets

    def bind_kernel(self, kernel: Kernel) -> None:
        self._kernel = kernel

    @property
    def kernel(self) -> Kernel:
        if self._kernel is None:
            raise RuntimeError(
                "kernel not bound — process.spawn and schedule.at "
                "require a running Kernel."
            )
        return self._kernel

    def space_for_process(self, process_id) -> str:
        if self.goal_registry is None:
            from emergence.spaces.registry import DEFAULT_SPACE_ID

            return DEFAULT_SPACE_ID
        goal_id = self.goal_registry.goal_for_process(process_id)
        if goal_id is None:
            from emergence.spaces.registry import DEFAULT_SPACE_ID

            return DEFAULT_SPACE_ID
        record = self.goal_registry.get(goal_id)
        if record is None:
            from emergence.spaces.registry import DEFAULT_SPACE_ID

            return DEFAULT_SPACE_ID
        return record.space_id
