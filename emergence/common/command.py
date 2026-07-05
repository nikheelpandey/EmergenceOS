from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from emergence.common.message import Message


@dataclass(slots=True, kw_only=True)
class Command(Message):
    """
    A Command instructs a process to perform a specific action.

    Unlike a Request, a Command represents an imperative instruction.
    Whether the receiver sends a Response is implementation-specific.
    """

    action: str

    arguments: dict[str, Any] | None = None
