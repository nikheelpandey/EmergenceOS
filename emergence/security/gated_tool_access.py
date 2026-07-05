from __future__ import annotations

from emergence.core.ids import ProcessID
from emergence.executor.tool_executor import ToolExecutor
from emergence.executor.tool_model import ToolRequest, ToolResult
from emergence.executor.tool_executor import capability_for_tool
from emergence.security.security_manager import SecurityManager


class GatedToolAccess:
    """
    Capability-gated tool invocation facade for ProcessContext.
    """

    def __init__(
        self,
        tool_executor: ToolExecutor,
        security: SecurityManager,
        process_id: ProcessID,
    ) -> None:
        self._executor = tool_executor
        self._security = security
        self._process_id = process_id
        self._pid = str(process_id)

    def invoke(
        self,
        tool_name: str,
        arguments: dict | None = None,
    ) -> ToolResult:
        self._security.require(
            self._pid,
            capability_for_tool(tool_name),
            operation=f"tools.invoke('{tool_name}')",
        )
        request = ToolRequest(
            tool_name=tool_name,
            arguments=arguments or {},
        )
        return self._executor.execute(request, self._process_id)
