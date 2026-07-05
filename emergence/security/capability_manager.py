from __future__ import annotations

from collections import defaultdict

from emergence.security.capability import Capability


class CapabilityManager:
    """
    Manages the capabilities granted to every process.

    The CapabilityManager is the kernel's authorization service.
    Before a process accesses a protected resource, the kernel
    consults this manager to determine whether the operation is
    permitted.
    """

    def __init__(self) -> None:
        self._capabilities: dict[str, set[Capability]] = defaultdict(set)

    def grant(self, pid: str, capability: Capability) -> None:
        """
        Grant a capability to a process.
        """
        self._capabilities[pid].add(capability)

    def revoke(self, pid: str, capability: Capability) -> None:
        """
        Revoke a capability from a process.
        """
        self._capabilities[pid].discard(capability)

    def has(self, pid: str, capability: Capability) -> bool:
        """
        Return True if the process possesses the capability.
        """
        return capability in self._capabilities.get(pid, set())

    def capabilities(self, pid: str) -> set[Capability]:
        """
        Return all capabilities granted to a process.
        """
        return set(self._capabilities.get(pid, set()))

    def clear(self, pid: str) -> None:
        """
        Remove every capability from a process.
        """
        self._capabilities.pop(pid, None)

    def clear_all(self) -> None:
        """
        Remove all capabilities from every process.
        """
        self._capabilities.clear()