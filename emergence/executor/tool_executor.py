from __future__ import annotations

from typing import Any, Callable

from emergence.core.budget_tracker import BudgetTracker
from emergence.core.event import Event
from emergence.core.ids import ProcessID
from emergence.events.event_bus import EventBus
from emergence.executor.tool_model import (
    ToolCompletedEvent,
    ToolFailedEvent,
    ToolRequest,
    ToolResult,
    ToolRequestedEvent,
)
from emergence.security.capabilities import TOOL_PYTHON
from emergence.security.errors import PermissionDeniedError
from emergence.security.security_manager import SecurityManager

ToolHandler = Callable[[dict[str, Any]], Any]


class ToolRegistry:
    """
    Registry of invocable tools.

    Tools are only accessible through the Executor — processes
    never invoke tools directly.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolHandler] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        self._tools[name] = handler

    def has(self, name: str) -> bool:
        return name in self._tools

    def invoke(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            handler = self._tools[name]
        except KeyError as exc:
            raise KeyError(
                f"No tool registered for '{name}'."
            ) from exc
        return handler(arguments)


class ToolExecutor:
    """
    Executes tool requests on behalf of processes.

    Publishes tool lifecycle events and decrements budgets.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        event_bus: EventBus,
        security: SecurityManager,
        budgets: BudgetTracker,
    ) -> None:
        self._registry = registry
        self._event_bus = event_bus
        self._security = security
        self._budgets = budgets

    def execute(
        self,
        request: ToolRequest,
        process_id: ProcessID,
    ) -> ToolResult:
        pid = str(process_id)

        self._security.require(
            pid,
            TOOL_PYTHON,
            operation=f"tool.invoke('{request.tool_name}')",
        )

        requested = ToolRequestedEvent(
            tool_name=request.tool_name,
            request_id=request.request_id,
            source_process=process_id,
            payload={"arguments": request.arguments},
        )
        self._event_bus.publish(requested)

        try:
            result = self._registry.invoke(
                request.tool_name,
                request.arguments,
            )
            self._budgets.record_execution(
                process_id,
                tool_invocations=1,
            )
            self._event_bus.publish(
                ToolCompletedEvent(
                    tool_name=request.tool_name,
                    request_id=request.request_id,
                    source_process=process_id,
                    causation_id=requested.event_id,
                    correlation_id=requested.correlation_id,
                    payload={"result": result},
                )
            )
            return ToolResult(
                request_id=request.request_id,
                success=True,
                result=result,
            )
        except Exception as exc:
            self._event_bus.publish(
                ToolFailedEvent(
                    tool_name=request.tool_name,
                    request_id=request.request_id,
                    source_process=process_id,
                    error=str(exc),
                    causation_id=requested.event_id,
                    correlation_id=requested.correlation_id,
                )
            )
            return ToolResult(
                request_id=request.request_id,
                success=False,
                error=str(exc),
            )
