from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from emergence.common.message import Message


@dataclass(slots=True, kw_only=True)
class Notification(Message):
    """
    A one-way message that informs another process that
    something has happened.

    Notifications do not expect a response.
    """

    topic: str

    data: Any | None = None
