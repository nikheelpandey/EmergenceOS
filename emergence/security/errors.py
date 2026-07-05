from __future__ import annotations

from emergence.security.capability import Capability


class PermissionDeniedError(Exception):
    """
    Raised when a process attempts an operation without the
    required capability.
    """

    def __init__(
        self,
        pid: str,
        capability: Capability,
        *,
        operation: str | None = None,
    ) -> None:
        self.pid = pid
        self.capability = capability
        self.operation = operation

        detail = operation or capability.name
        super().__init__(
            f"Process '{pid}' lacks capability '{capability.name}' "
            f"required for {detail}."
        )
