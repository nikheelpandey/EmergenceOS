from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from emergence.core.event import Event, EventType
from emergence.core.ids import ProcessID


@dataclass(frozen=True, slots=True)
class ToolRequest:
    """A request to invoke a tool through the Executor."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Result of a tool invocation."""

    request_id: str
    success: bool
    result: Any = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ToolRequestedEvent(Event):
    tool_name: str = ""
    request_id: str = ""
    event_type: EventType = field(
        default=EventType.TOOL_REQUESTED,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class ToolCompletedEvent(Event):
    tool_name: str = ""
    request_id: str = ""
    success: bool = True
    event_type: EventType = field(
        default=EventType.TOOL_COMPLETED,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class ToolFailedEvent(Event):
    tool_name: str = ""
    request_id: str = ""
    error: str = ""
    event_type: EventType = field(
        default=EventType.TOOL_FAILED,
        init=False,
    )
