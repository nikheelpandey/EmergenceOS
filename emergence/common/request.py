from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from emergence.common.message import Message


@dataclass(slots=True, kw_only=True)
class Request(Message):
    """
    A request sent from one process to another.

    Requests are a specialized Message that expect a corresponding
    Response carrying the same correlation_id.
    """

    action: str
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
