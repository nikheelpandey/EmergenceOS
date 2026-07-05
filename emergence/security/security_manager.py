from __future__ import annotations

from emergence.security.capability import Capability
from emergence.security.capability_manager import CapabilityManager
from emergence.security.errors import PermissionDeniedError


class SecurityManager:
    """
    Central authorization service for kernel-gated operations.

    Every protected resource consults this manager before allowing
    a process to proceed.
    """

    def __init__(self, capabilities: CapabilityManager) -> None:
        self._capabilities = capabilities

    @property
    def capability_manager(self) -> CapabilityManager:
        return self._capabilities

    def require(
        self,
        pid: str,
        capability: Capability,
        *,
        operation: str | None = None,
    ) -> None:
        """
        Assert that a process holds the given capability.

        Raises
        ------
        PermissionDeniedError
            If the capability is not granted.
        """
        if not self._capabilities.has(pid, capability):
            raise PermissionDeniedError(
                pid,
                capability,
                operation=operation,
            )

    def check(
        self,
        pid: str,
        capability: Capability,
    ) -> bool:
        """Return True if the process holds the capability."""
        return self._capabilities.has(pid, capability)
