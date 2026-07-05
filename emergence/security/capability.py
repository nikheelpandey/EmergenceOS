from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Capability:
    """
    Represents a permission granted to a process.

    Capabilities are issued by the kernel and determine what a
    process is allowed to access or execute.

    Examples:
        - state.read
        - state.write
        - memory.read
        - memory.write
        - tool.browser
        - tool.python
        - filesystem.read
    """

    name: str
    description: str | None = None

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(self.name)