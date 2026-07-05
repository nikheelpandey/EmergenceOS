from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from emergence.common.message import Message


@dataclass(slots=True, kw_only=True)
class Response(Message):
    """
    Represents the result of a previously issued Request.

    Responses are correlated back to the originating Request
    using the correlation_id.
    """

    correlation_id: str

    success: bool = True

    result: Any | None = None

    error: str | None = None
